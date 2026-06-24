import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def _get_llm(api_key: str, temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    if not api_key:
        raise ValueError("Google API Key is required.")
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=api_key,
        temperature=temperature,
    )


def generate_sql(db_schema: str, user_query: str, context_docs: list, api_key: str) -> str:
    """Generate a safe SQLite SELECT query from a natural-language question."""
    llm = _get_llm(api_key, temperature=0.0)

    context_str = ""
    if context_docs:
        context_str = "\nRelevant Domain Knowledge:\n"
        for i, doc in enumerate(context_docs):
            context_str += f"[{i+1}] (Source: {doc['source']}): {doc['content']}\n"

    system_prompt = """You are a highly skilled SQL Analyst specialising in SQLite.
Write ONE clean, valid SQLite SELECT query to answer the user's question.

Database Schema:
{schema}
{context}

Rules:
1. Output ONLY the raw SQL. No markdown fences, no explanation.
2. Only SELECT or WITH (CTE) statements — never INSERT/UPDATE/DELETE/DROP/ALTER.
3. Use only tables and columns from the schema above.
4. For dates use strftime('%Y', col) etc. — SQLite does NOT support EXTRACT or TO_DATE.
5. Always alias aggregated columns (e.g. SUM(o.total_amount) AS total_sales).

User Question: {question}
SQL Query:"""

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt)])
    chain = prompt | llm | StrOutputParser()
    sql = chain.invoke({"schema": db_schema, "context": context_str, "question": user_query}).strip()

    for fence in ("```sql", "```"):
        if sql.startswith(fence):
            sql = sql[len(fence):]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


def explain_results(user_query: str, sql_query: str, query_results: dict, api_key: str) -> str:
    """Translate raw tabular results into a plain-English business summary."""
    llm = _get_llm(api_key, temperature=0.2)

    system_prompt = """You are a professional Business Intelligence Analyst.
Explain the SQL query results to a business user in plain English (max 150 words).
Highlight key insights: trends, totals, outliers, or comparisons.
If the result is empty, say so clearly.

User Question: {question}
SQL Executed: {sql}
Results (JSON): {results}"""

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt)])
    chain = prompt | llm | StrOutputParser()
    results_str = json.dumps(query_results.get("data", [])[:20], indent=2)
    return chain.invoke({"question": user_query, "sql": sql_query, "results": results_str}).strip()


def recommend_chart(columns: list, data: list, api_key: str) -> dict:
    """Suggest the best Altair chart type and axis mapping for the result set."""
    if not data:
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "No data to chart."}

    llm = _get_llm(api_key, temperature=0.0)

    system_prompt = """You are a Data Visualisation expert.
Return ONLY a raw JSON object (no markdown) with these keys:
- chart_type: "bar" | "line" | "pie" | "metric" | "none"
- x_axis: column name for x-axis (null for metric/none)
- y_axis: column name for y-axis / numeric value (null for metric/none)
- explanation: one-sentence reason

Selection rules:
1. "line"   → time-series data (date/month/year on x-axis)
2. "bar"    → category comparison (text labels on x-axis)
3. "pie"    → part-of-whole with < 7 categories
4. "metric" → single-row single-numeric result
5. "none"   → complex multi-column tables or text-only

Columns: {columns}
Sample rows (up to 3): {sample}"""

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt)])
    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke({"columns": str(columns), "sample": str(data[:3])}).strip()

    for fence in ("```json", "```"):
        if raw.startswith(fence):
            raw = raw[len(fence):]
    if raw.endswith("```"):
        raw = raw[:-3]
    try:
        return json.loads(raw.strip())
    except Exception:
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "Could not parse recommendation."}
