import streamlit as st
import requests
import pandas as pd
import os
import json
import altair as alt
import sys

# Add project root to python path to support standalone import
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# Try importing backend functions to support standalone deployment fallback
try:
    from backend.database import init_database, get_db_schema, execute_safe_query
    from backend.vector_store import SchemaKnowledgeBase
    from backend.copilot import generate_sql, explain_results, recommend_chart
    HAS_LOCAL_BACKEND_CODE = True
except ImportError:
    HAS_LOCAL_BACKEND_CODE = False

# Page Configuration
st.set_page_config(
    page_title="Analytics Q&A Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL
API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

# Paths
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "sample_business.db")
FAISS_INDEX_DIR = os.path.join(PROJECT_ROOT, "data", "faiss_index")
SAVED_QUESTIONS_FILE = os.path.join(PROJECT_ROOT, "data", "saved_questions.json")

# Initialize vector store for standalone mode
if HAS_LOCAL_BACKEND_CODE:
    vector_kb = SchemaKnowledgeBase(index_dir=FAISS_INDEX_DIR)

# Load Custom Stylesheet
styles_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(styles_path):
    with open(styles_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_key" not in st.session_state:
    api_key_val = ""
    # 1. Try Streamlit Secrets (for Cloud deployment)
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            api_key_val = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass
    
    # 2. Try OS environment variable if secrets are empty
    if not api_key_val:
        api_key_val = os.environ.get("GOOGLE_API_KEY", "")
        
    st.session_state.api_key = api_key_val

if "db_path" not in st.session_state:
    st.session_state.db_path = None
if "selected_question" not in st.session_state:
    st.session_state.selected_question = None

# Helper functions for standalone mode
def load_saved_questions_local() -> list:
    default_questions = [
        {"question": "List the top 5 customers by total order amount.", "description": "Returns highest purchasing customers with sum of their order values.", "category": "Sales"},
        {"question": "Show total sales category-wise for each month in 2025.", "description": "Displays monthly product category sales trends.", "category": "Trends"},
        {"question": "How many orders were cancelled and what was their total value?", "description": "Checks for cancelled orders count and sum.", "category": "Operations"},
        {"question": "Compare our total sales against the target for each category in March 2025.", "description": "Compares orders revenue with sales targets.", "category": "Performance"},
        {"question": "Show the list of products that have less than 50 units in stock.", "description": "Filters products with low stock levels.", "category": "Inventory"}
    ]
    if not os.path.exists(SAVED_QUESTIONS_FILE):
        os.makedirs(os.path.dirname(SAVED_QUESTIONS_FILE), exist_ok=True)
        with open(SAVED_QUESTIONS_FILE, "w") as f:
            json.dump(default_questions, f, indent=2)
        return default_questions
    try:
        with open(SAVED_QUESTIONS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return default_questions

def add_saved_question_local(q: dict):
    questions = load_saved_questions_local()
    if not any(item["question"].lower() == q["question"].lower() for item in questions):
        questions.append(q)
        with open(SAVED_QUESTIONS_FILE, "w") as f:
            json.dump(questions, f, indent=2)

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # 1. API Key Input
    api_key_input = st.text_input(
        "Gemini API Key",
        value=st.session_state.api_key,
        type="password",
        help="Input your Gemini API key (Google AI Studio) to power the Copilot."
    )
    if api_key_input != st.session_state.api_key:
        st.session_state.api_key = api_key_input
        st.success("API Key updated!")
        st.session_state.messages = [] # Clear history on key change to reset chains
        st.rerun()
        
    st.markdown("<hr class='custom-hr'/>", unsafe_allow_html=True)
    
    # 2. Custom Database Upload
    st.markdown("### 🗄️ Database Settings")
    uploaded_db = st.file_uploader(
        "Connect Custom SQLite DB",
        type=["db", "sqlite", "sqlite3"],
        help="Upload a custom SQLite database file to query your own schema."
    )
    
    if uploaded_db is not None:
        upload_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(upload_dir, exist_ok=True)
        custom_db_path = os.path.join(upload_dir, "uploaded_database.db")
        
        with open(custom_db_path, "wb") as f:
            f.write(uploaded_db.getbuffer())
            
        if st.session_state.db_path != custom_db_path:
            st.session_state.db_path = custom_db_path
            st.success(f"Connected to: {uploaded_db.name}")
            st.session_state.messages = []
            st.rerun()
            
    if st.session_state.db_path is not None:
        if st.button("Reset to Default Sample DB"):
            st.session_state.db_path = None
            st.success("Reset to sample database.")
            st.session_state.messages = []
            st.rerun()

    st.markdown("<hr class='custom-hr'/>", unsafe_allow_html=True)

    # 3. Knowledge Base Upload
    st.markdown("### 📚 Knowledge Base Docs")
    st.markdown("<p style='font-size: 0.85rem; color: #a0aec0;'>Upload data glossary, dictionary, or rules to teach the Copilot about business terms.</p>", unsafe_allow_html=True)
    uploaded_doc = st.file_uploader(
        "Upload Text/Markdown Guide",
        type=["txt", "md"],
        help="The content will be indexed in the vector store and retrieved during queries."
    )
    
    if uploaded_doc is not None:
        if not st.session_state.api_key:
            st.warning("Please provide a Gemini API Key first to generate embeddings.")
        else:
            with st.spinner("Indexing document..."):
                # Try HTTP call to backend first
                backend_success = False
                try:
                    files = {"file": (uploaded_doc.name, uploaded_doc.getvalue(), "text/plain")}
                    data = {"api_key": st.session_state.api_key}
                    response = requests.post(f"{API_URL}/api/upload-doc", files=files, data=data)
                    if response.status_code == 200:
                        st.success(response.json()["message"])
                        backend_success = True
                except Exception:
                    pass
                
                # Standalone fallback if API fails/offline
                if not backend_success and HAS_LOCAL_BACKEND_CODE:
                    try:
                        text_content = uploaded_doc.getvalue().decode("utf-8", errors="ignore")
                        vector_kb.add_document(
                            text_content=text_content,
                            source_name=uploaded_doc.name,
                            api_key=st.session_state.api_key
                        )
                        st.success(f"Indexed {uploaded_doc.name} successfully (Standalone Mode).")
                    except Exception as e:
                        st.error(f"Failed to index document: {e}")
                    
    if st.button("Clear Knowledge Base", help="Resets the indexed documents in vector store"):
        # Try API
        backend_success = False
        try:
            response = requests.post(f"{API_URL}/api/reset-knowledge")
            if response.status_code == 200:
                st.success("Vector store reset complete.")
                backend_success = True
        except Exception:
            pass
            
        # Standalone
        if not backend_success and HAS_LOCAL_BACKEND_CODE:
            if vector_kb.reset():
                st.success("Vector store reset complete (Standalone Mode).")

# Header Area
st.markdown("<div class='title-gradient'>Analytics Q&A Copilot</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle-text'>Natural-language database explorer powered by Gemini & FastAPI</div>", unsafe_allow_html=True)

# Main Application Layout - Tabs
tab_chat, tab_schema = st.tabs(["💬 Assistant Chat", "🗂️ Database Schema"])

# Active DB Path resolution
active_db = st.session_state.db_path if st.session_state.db_path else DEFAULT_DB_PATH

# 1. Fetch Schema Details
schema_text = ""
is_standalone_mode = True
backend_url_display = "Offline (Running in Standalone Serverless Mode)"

try:
    params = {}
    if st.session_state.db_path:
        params["db_path"] = st.session_state.db_path
    schema_res = requests.get(f"{API_URL}/api/schema", params=params, timeout=2)
    if schema_res.status_code == 200:
        schema_text = schema_res.json().get("schema", "")
        is_standalone_mode = False
        backend_url_display = f"Online ({API_URL})"
except Exception:
    is_standalone_mode = True

# Fallback schema loading
if is_standalone_mode and HAS_LOCAL_BACKEND_CODE:
    init_database(active_db)
    schema_text = get_db_schema(active_db)

# Render Database Schema Tab
with tab_schema:
    st.markdown(f"**Connected Database File:** `{active_db}`")
    st.markdown(f"**Backend API Server Status:** `{backend_url_display}`")
    
    # Display statistics
    tables = [line.split("Table: ")[1] for line in schema_text.split("
") if line.startswith("Table: ")]
    
    st.markdown(f"""
    <div class='metric-container'>
        <div class='metric-card'>
            <h3>Active Schema</h3>
            <p>SQLite</p>
        </div>
        <div class='metric-card'>
            <h3>Tables Detected</h3>
            <p>{len(tables)}</p>
        </div>
        <div class='metric-card'>
            <h3>Connection Status</h3>
            <p style="color: #4ade80;">Active</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### Schema Structure")
    st.code(schema_text, language="text")

# Render Assistant Chat Tab
with tab_chat:
    # Load questions (API or local)
    saved_qs = []
    try:
        if not is_standalone_mode:
            q_res = requests.get(f"{API_URL}/api/saved-questions", timeout=2)
            if q_res.status_code == 200:
                saved_qs = q_res.json()
    except Exception:
        pass
        
    if not saved_qs and HAS_LOCAL_BACKEND_CODE:
        saved_qs = load_saved_questions_local()

    # 1. Suggested Questions
    st.markdown("##### 💡 Suggested Questions")
    cols = st.columns(len(saved_qs))
    for idx, q_item in enumerate(saved_qs):
        with cols[idx]:
            if st.button(q_item["question"], key=f"sq_{idx}", help=q_item.get("description", "")):
                st.session_state.selected_question = q_item["question"]
                st.rerun()

    # 2. API Key Warning
    if not st.session_state.api_key:
        st.info("💡 To get started, please enter your Gemini API Key in the sidebar. You can get a free key from Google AI Studio.")

    # 3. Display Chat Messages
    st.markdown("<hr class='custom-hr'/>", unsafe_allow_html=True)
    
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div style="display: flex; justify-content: flex-end; margin-bottom: 1rem;">
                <div class="chat-bubble-user">
                    <b>You:</b><br/>{msg["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            res = msg["content"]
            with st.container():
                st.markdown(f"""
                <div style="display: flex; justify-content: flex-start; margin-bottom: 0.5rem;">
                    <div class="chat-bubble-assistant">
                        <b>Assistant:</b><br/>{res.get('explanation', 'No explanation provided.')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Check for Chart Visualization
                chart_cfg = res.get("chart", {})
                data = res.get("data", [])
                
                if chart_cfg and chart_cfg.get("chart_type") != "none" and data:
                    df = pd.DataFrame(data)
                    x_col = chart_cfg.get("x_axis")
                    y_col = chart_cfg.get("y_axis")
                    c_type = chart_cfg.get("chart_type")
                    
                    if c_type == "metric" and y_col in df.columns:
                        val = df[y_col].iloc[0]
                        if isinstance(val, float):
                            val = f"${val:,.2f}"
                        elif isinstance(val, (int, float)):
                            val = f"{val:,}"
                        st.metric(label=y_col, value=val)
                        
                    elif c_type == "bar" and x_col in df.columns and y_col in df.columns:
                        chart = alt.Chart(df).mark_bar(
                            cornerRadiusTopLeft=8,
                            cornerRadiusTopRight=8,
                            color='#4D96FF'
                        ).encode(
                            x=alt.X(x_col, sort=None, title=x_col),
                            y=alt.Y(y_col, title=y_col),
                            tooltip=list(df.columns)
                        ).properties(
                            width=600,
                            height=350
                        ).configure_view(
                            strokeWidth=0
                        )
                        st.altair_chart(chart, use_container_width=True)
                        
                    elif c_type == "line" and x_col in df.columns and y_col in df.columns:
                        chart = alt.Chart(df).mark_line(
                            point=True,
                            color='#FF6B6B',
                            strokeWidth=3
                        ).encode(
                            x=alt.X(x_col, sort=None, title=x_col),
                            y=alt.Y(y_col, title=y_col),
                            tooltip=list(df.columns)
                        ).properties(
                            width=600,
                            height=350
                        )
                        st.altair_chart(chart, use_container_width=True)
                        
                    elif c_type == "pie" and x_col in df.columns and y_col in df.columns:
                        chart = alt.Chart(df).mark_arc(innerRadius=50).encode(
                            theta=alt.Theta(field=y_col, type="quantitative"),
                            color=alt.Color(field=x_col, type="nominal", scale=alt.Scale(scheme="category10")),
                            tooltip=list(df.columns)
                        ).properties(
                            width=400,
                            height=300
                        )
                        st.altair_chart(chart, use_container_width=True)
                        
                # Collapsible Details Expander
                with st.expander("🔍 View SQL Query and Raw Output"):
                    st.markdown("**Executed SQL Query:**")
                    st.code(res.get("query", ""), language="sql")
                    
                    if data:
                        st.markdown("**Result Dataset:**")
                        st.dataframe(pd.DataFrame(data), use_container_width=True)
                    else:
                        st.warning("No data rows returned by the query.")
                        
                # Citations Box
                citations = res.get("citations", [])
                if citations:
                    st.markdown("**📚 Vector Citations / Source Context:**")
                    for cit in citations:
                        st.markdown(f"""
                        <div class="citation-box">
                            <b>Source:</b> {cit.get('source', 'Unknown')}<br/>
                            {cit.get('content', '')}
                        </div>
                        """, unsafe_allow_html=True)
                        
                st.markdown("<hr style='border-top: 1px solid rgba(255,255,255,0.05); margin: 1.5rem 0;'/>", unsafe_allow_html=True)

    # 4. Handle Input
    prompt = None
    if st.session_state.selected_question:
        prompt = st.session_state.selected_question
        st.session_state.selected_question = None  # Reset trigger
    else:
        chat_inp = st.chat_input("Ask a question (e.g., 'What was the sales target in March 2025?')")
        if chat_inp:
            prompt = chat_inp

    if prompt:
        if not st.session_state.api_key:
            st.error("⚠️ Please configure your Gemini API Key in the sidebar before asking questions.")
        else:
            # Append User Question
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Query pipeline
            with st.spinner("Analyzing schema, generating query and fetching results..."):
                response_success = False
                res_json = {}
                
                # 1. Try FastAPI backend first
                if not is_standalone_mode:
                    try:
                        headers = {"X-API-Key": st.session_state.api_key}
                        payload = {"query": prompt}
                        if st.session_state.db_path:
                            payload["db_path"] = st.session_state.db_path
                            
                        response = requests.post(f"{API_URL}/api/query", headers=headers, json=payload, timeout=15)
                        if response.status_code == 200:
                            res_json = response.json()
                            response_success = True
                    except Exception:
                        pass
                
                # 2. Standalone fallback (Executes chains locally in python)
                if not response_success and HAS_LOCAL_BACKEND_CODE:
                    try:
                        # Vector search
                        citations = []
                        try:
                            citations = vector_kb.search(prompt, api_key=st.session_state.api_key, k=2)
                        except Exception:
                            pass
                        
                        # Generate SQL
                        generated_sql = generate_sql(
                            db_schema=schema_text,
                            user_query=prompt,
                            context_docs=citations,
                            api_key=st.session_state.api_key
                        )
                        
                        # Safe Execute
                        execution_result = execute_safe_query(active_db, generated_sql)
                        
                        if not execution_result.get("success", False):
                            res_json = {
                                "success": False,
                                "query": generated_sql,
                                "error": execution_result.get("error", "Unknown database error."),
                                "citations": citations
                            }
                        else:
                            # Explain
                            explanation = explain_results(
                                user_query=prompt,
                                sql_query=generated_sql,
                                query_results=execution_result,
                                api_key=st.session_state.api_key
                            )
                            
                            # Recommend chart
                            chart_recommendation = recommend_chart(
                                columns=execution_result["columns"],
                                data=execution_result["data"],
                                api_key=st.session_state.api_key
                            )
                            
                            res_json = {
                                "success": True,
                                "query": generated_sql,
                                "columns": execution_result["columns"],
                                "data": execution_result["data"],
                                "row_count": execution_result["row_count"],
                                "explanation": explanation,
                                "chart": chart_recommendation,
                                "citations": citations
                            }
                        
                        response_success = True
                        
                        # Auto-save question locally
                        add_saved_question_local({
                            "question": prompt,
                            "description": f"User question: {prompt}",
                            "category": "Custom"
                        })
                    except Exception as e:
                        res_json = {
                            "success": False,
                            "error": f"Standalone pipeline execution failed: {str(e)}"
                        }
                
                # Append Response
                if response_success:
                    if res_json.get("success", False):
                        st.session_state.messages.append({"role": "assistant", "content": res_json})
                        # Save custom question via API if possible
                        if not is_standalone_mode:
                            try:
                                requests.post(f"{API_URL}/api/saved-questions", json={
                                    "question": prompt,
                                    "description": f"User question: {prompt}",
                                    "category": "Custom"
                                })
                            except Exception:
                                pass
                    else:
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": {
                                "explanation": f"❌ Query Execution Failed: {res_json.get('error')}",
                                "query": res_json.get("query", "No query generated."),
                                "data": [],
                                "chart": {"chart_type": "none"},
                                "citations": res_json.get("citations", [])
                            }
                        })
                else:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": {
                            "explanation": res_json.get("error", "🔌 Failed to execute pipeline in both API and Standalone modes."),
                            "query": "",
                            "data": [],
                            "chart": {"chart_type": "none"}
                        }
                    })
            st.rerun()
