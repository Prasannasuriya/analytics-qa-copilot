import os
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import json

from .database import init_database, get_db_schema, execute_safe_query
from .vector_store import SchemaKnowledgeBase
from .copilot import generate_sql, explain_results, recommend_chart

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "sample_business.db")
FAISS_INDEX_DIR = os.path.join(DATA_DIR, "faiss_index")
SAVED_QUESTIONS_FILE = os.path.join(DATA_DIR, "saved_questions.json")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize FastAPI
app = FastAPI(title="Analytics Q&A Copilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize vector store
vector_kb = SchemaKnowledgeBase(index_dir=FAISS_INDEX_DIR)

# Pydantic Models
class QueryRequest(BaseModel):
    query: str
    db_path: Optional[str] = None

class SavedQuestion(BaseModel):
    question: str
    description: Optional[str] = ""
    category: Optional[str] = "General"

# Helper for saved questions
def load_saved_questions() -> List[dict]:
    default_questions = [
        {"question": "List the top 5 customers by total order amount.", "description": "Returns highest purchasing customers with sum of their order values.", "category": "Sales"},
        {"question": "Show total sales category-wise for each month in 2025.", "description": "Displays monthly product category sales trends.", "category": "Trends"},
        {"question": "How many orders were cancelled and what was their total value?", "description": "Checks for cancelled orders count and sum.", "category": "Operations"},
        {"question": "Compare our total sales against the target for each category in March 2025.", "description": "Compares orders revenue with sales targets.", "category": "Performance"},
        {"question": "Show the list of products that have less than 50 units in stock.", "description": "Filters products with low stock levels.", "category": "Inventory"}
    ]
    if not os.path.exists(SAVED_QUESTIONS_FILE):
        with open(SAVED_QUESTIONS_FILE, "w") as f:
            json.dump(default_questions, f, indent=2)
        return default_questions
    try:
        with open(SAVED_QUESTIONS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return default_questions

def save_new_question(q: dict):
    questions = load_saved_questions()
    # Avoid duplicates
    if not any(item["question"].lower() == q["question"].lower() for item in questions):
        questions.append(q)
        with open(SAVED_QUESTIONS_FILE, "w") as f:
            json.dump(questions, f, indent=2)

@app.on_event("startup")
def startup_event():
    # Make sure default database is initialized
    init_database(DEFAULT_DB_PATH)

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "database": "initialized" if os.path.exists(DEFAULT_DB_PATH) else "missing"}

@app.get("/api/schema")
def get_schema(db_path: Optional[str] = None):
    target_db = db_path if db_path else DEFAULT_DB_PATH
    if not os.path.exists(target_db):
        init_database(target_db)
    
    schema_text = get_db_schema(target_db)
    return {
        "db_path": target_db,
        "schema": schema_text
    }

@app.post("/api/upload-doc")
async def upload_document(
    file: UploadFile = File(...),
    api_key: str = Form(...)
):
    if not api_key:
        raise HTTPException(status_code=400, detail="Google API Key is required for indexing.")
        
    try:
        content = await file.read()
        text_content = content.decode("utf-8", errors="ignore")
        
        success = vector_kb.add_document(
            text_content=text_content,
            source_name=file.filename,
            api_key=api_key
        )
        if success:
            return {"message": f"Successfully indexed {file.filename} in knowledge base."}
        else:
            raise HTTPException(status_code=500, detail="Failed to add document content to vector store.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {str(e)}")

@app.post("/api/reset-knowledge")
def reset_knowledge():
    success = vector_kb.reset()
    if success:
        return {"message": "Knowledge base vector store reset successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to reset vector store.")

@app.get("/api/saved-questions")
def get_questions():
    return load_saved_questions()

@app.post("/api/saved-questions")
def add_question(q: SavedQuestion):
    save_new_question(q.dict())
    return {"message": "Question saved successfully."}

@app.post("/api/query")
def run_copilot_query(
    request: QueryRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    api_key = x_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Google API Key is missing. Please provide it in the X-API-Key header.")

    target_db = request.db_path if request.db_path else DEFAULT_DB_PATH
    if not os.path.exists(target_db):
        init_database(target_db)

    # 1. Schema Retrieval
    db_schema = get_db_schema(target_db)
    
    # 2. Vector KB Retrieval for Citations & Context
    citations = []
    try:
        citations = vector_kb.search(request.query, api_key=api_key, k=2)
    except Exception as e:
        print(f"Vector search failed (skipping context): {e}")

    # 3. Generate SQL Query
    try:
        generated_sql = generate_sql(
            db_schema=db_schema,
            user_query=request.query,
            context_docs=citations,
            api_key=api_key
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during SQL generation: {str(e)}")

    # 4. Safe Execute SQL
    execution_result = execute_safe_query(target_db, generated_sql)
    
    if not execution_result.get("success", False):
        # Even if query failed, return the details so frontend can show SQL and Error details
        return {
            "success": False,
            "query": generated_sql,
            "error": execution_result.get("error", "Unknown database execution error."),
            "citations": citations
        }

    # 5. Explain Results
    try:
        explanation = explain_results(
            user_query=request.query,
            sql_query=generated_sql,
            query_results=execution_result,
            api_key=api_key
        )
    except Exception as e:
        explanation = f"Query executed successfully, but explanation failed: {str(e)}"

    # 6. Recommend Chart
    try:
        chart_recommendation = recommend_chart(
            columns=execution_result["columns"],
            data=execution_result["data"],
            api_key=api_key
        )
    except Exception as e:
        chart_recommendation = {
            "chart_type": "none",
            "x_axis": None,
            "y_axis": None,
            "explanation": f"Chart recommendation failed: {str(e)}"
        }

    # Return full copilot pipeline result
    return {
        "success": True,
        "query": generated_sql,
        "columns": execution_result["columns"],
        "data": execution_result["data"],
        "row_count": execution_result["row_count"],
        "explanation": explanation,
        "chart": chart_recommendation,
        "citations": citations
    }
