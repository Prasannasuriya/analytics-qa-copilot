import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def _get_llm(api_key: str, temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """
    Initializes a ChatGoogleGenerativeAI instance with the provided API key.
    """
    if not api_key:
        raise ValueError("Google API Key is required to call Gemini models.")
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key,
        temperature=temperature
    )

def generate_sql(db_schema: str, user_query: str, context_docs: list, api_key: str) -> str:
    """
    Generates a valid SQLite SQL query to answer the user's question,
    using the schema and any relevant knowledge base documentation.
    """
    llm = _get_llm(api_key, temperature=0.0)
    
    # Format context docs if present
    context_str = ""
    if context_docs:
        context_str = "\nRelevant Domain Knowledge & Guidelines:\n"
        for i, doc in enumerate(context_docs):
            context_str += f"[{i+1}] (Source: {doc['source']}): {doc['content']}\n"
            
    system_prompt = """You are a highly skilled SQL Analyst specializing in SQLite.
Your task is to write a clean, efficient, and valid SQLite query to answer the user's natural language question based ONLY on the provided schema and guidelines.

Database Schema:
{schema}
{context}

Safety and Formatting Rules:
1. You must ONLY output the raw SQL query. Do not wrap it in explanations or markdown block formatting.
2. Only write read-only queries (SELECT statements). Do not write queries with INSERT, UPDATE, DELETE, DROP, etc.
3. Be schema-aware: Only use the tables and columns defined in the schema.
4. When joining tables, always use explicit table aliases and prefix columns with their respective tables.
5. If table/column names contain spaces or special characters, wrap them in double quotes.
6. SQLite does not support complex functions like TO_DATE or EXTRACT. Use standard date functions like strftime('%Y-%m-%d', column) or strftime('%Y', column) if needed.
7. Return the query that answers the question directly.

User Question: {question}
SQL Query:"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt)
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    result = chain.invoke({
        "schema": db_schema,
        "context": context_str,
        "question": user_query
    })
    
    # Post-process cleanup of the query
    sql = result.strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()

def explain_results(user_query: str, sql_query: str, query_results: dict, api_key: str) -> str:
    """
    Generates a natural language explanation of the database results in business context.
    """
    llm = _get_llm(api_key, temperature=0.2)
    
    system_prompt = """You are a professional Business Intelligence Analyst.
Your task is to explain the results of a SQL query in plain English to a business user.
Be concise, accurate, and focus on highlighting key insights (trends, totals, outliers, comparisons).

User's Original Question: {question}
SQL Query Executed: {sql}
Query Results (JSON):
{results}

Write a professional summary explaining what these results mean in response to the user's question. If the results are empty, state that no data was found matching the criteria. Keep the explanation under 150 words."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt)
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    # Format the results for readability
    results_str = json.dumps(query_results.get("data", []), indent=2)
    
    return chain.invoke({
        "question": user_query,
        "sql": sql_query,
        "results": results_str
    }).strip()

def recommend_chart(columns: list, data: list, api_key: str) -> dict:
    """
    Analyzes columns and data values to suggest the best visualization.
    Returns a dictionary with format:
    {
      "chart_type": "bar" | "line" | "pie" | "metric" | "none",
      "x_axis": "column_name",
      "y_axis": "column_name",
      "explanation": "..."
    }
    """
    # If no data or single item, charts might not make sense
    if not data or len(data) == 0:
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "No data available to chart."}
        
    llm = _get_llm(api_key, temperature=0.0)
    
    system_prompt = """You are a Data Visualization expert.
Given a dataset schema and sample rows, recommend the absolute best visualization type.
Respond ONLY with a raw JSON object containing these keys:
- chart_type: must be one of: "bar", "line", "pie", "metric" (use for single numeric value), or "none".
- x_axis: the column to use on the horizontal axis (or categorizing column for pie chart). Null if chart_type is "metric" or "none".
- y_axis: the column to use on the vertical axis (numerical value to plot). Null if chart_type is "metric" or "none".
- explanation: a brief 1-sentence explanation of why this chart fits the data.

Rules for Chart Selection:
1. Use "line" for sequential time series data (e.g., date, month, year on x-axis).
2. Use "bar" for comparison of categories (e.g., product name, country, status on x-axis).
3. Use "pie" for part-to-whole relationships with small number of categories (< 7 categories).
4. Use "metric" if the result has 1 row and 1 numeric column (e.g. Total Revenue = $50,000).
5. Use "none" for complex tables with too many dimensions, text-only results, or when columns are not numeric.

Columns: {columns}
Sample Data (up to 3 rows): {sample}

Your JSON response:"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt)
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    sample_data = data[:3]
    
    result = chain.invoke({
        "columns": str(columns),
        "sample": str(sample_data)
    }).strip()
    
    # Parse JSON output safely
    try:
        # Clean any markdown code blocks
        clean_result = result
        if clean_result.startswith("```json"):
            clean_result = clean_result[7:]
        if clean_result.startswith("```"):
            clean_result = clean_result[3:]
        if clean_result.endswith("```"):
            clean_result = clean_result[:-3]
        clean_result = clean_result.strip()
        
        chart_config = json.loads(clean_result)
        return chart_config
    except Exception as e:
        print(f"Error parsing chart recommendation: {e}. Output was: {result}")
        # Default fallback
        return {
            "chart_type": "none",
            "x_axis": None,
            "y_axis": None,
            "explanation": "Failed to parse visualization recommendation."
        }
