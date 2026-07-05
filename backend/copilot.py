"""
Analytics Q&A Copilot — LLM pipeline
Uses google-generativeai SDK directly (bypasses LangChain prompt formatting issues).
"""
import json
import google.generativeai as genai


def _get_model(api_key: str, temperature: float = 0.0):
    if not api_key:
        raise ValueError("Google API Key is required.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=genai.types.GenerationConfig(temperature=temperature),
    )


def generate_sql(db_schema: str, user_query: str, context_docs: list, api_key: str) -> str:
    """Generate a safe SQLite SELECT query from a natural-language question."""
    if not db_schema or not db_schema.strip():
        raise ValueError(
            "Database schema is empty — the database may still be initializing. "
            "Please wait a moment and try again."
        )
    if not user_query or not user_query.strip():
        raise ValueError("Question is empty.")

    context_str = ""
    if context_docs:
        context_str = "\nRelevant Domain Knowledge:\n"
        for i, doc in enumerate(context_docs):
            context_str += f"[{i+1}] (Source: {doc['source']}): {doc['content']}\n"

    prompt = f"""You are a highly skilled SQL Analyst specialising in SQLite.
Write ONE clean, valid SQLite SELECT query to answer the user's question.

Database Schema:
{db_schema}
{context_str}

Rules:
1. Output ONLY the raw SQL. No markdown fences, no explanation.
2. Only SELECT or WITH (CTE) statements — never INSERT/UPDATE/DELETE/DROP/ALTER.
3. Use only tables and columns from the schema above.
4. For dates use strftime('%Y', col) etc. — SQLite does NOT support EXTRACT or TO_DATE.
5. Always alias aggregated columns (e.g. SUM(o.total_amount) AS total_sales).
6. Check the actual status values in the schema before filtering by status.

User Question: {user_query}
SQL Query:"""

    model = _get_model(api_key, temperature=0.0)
    response = model.generate_content(prompt)
    sql = response.text.strip()

    # Strip markdown fences if present
    for fence in ("```sql", "```"):
        if sql.startswith(fence):
            sql = sql[len(fence):]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


def explain_results(user_query: str, sql_query: str, query_results: dict, api_key: str) -> str:
    """Translate raw tabular results into a plain-English business summary."""
    if not user_query or not api_key:
        return "Unable to generate explanation."

    data = query_results.get("data", [])
    results_str = json.dumps(data[:20], indent=2) if data else "No rows returned."

    prompt = f"""You are a professional Business Intelligence Analyst.
Explain the SQL query results to a business user in plain English (max 150 words).
Highlight key insights: trends, totals, outliers, or comparisons.
If the result is empty, say so clearly.

User Question: {user_query}
SQL Executed: {sql_query}
Results (JSON): {results_str}

Explanation:"""

    try:
        model = _get_model(api_key, temperature=0.2)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Could not generate explanation: {e}"


def recommend_chart(columns: list, data: list, api_key: str) -> dict:
    """Suggest the best Altair chart type and axis mapping for the result set."""
    if not data or not columns:
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "No data to chart."}

    if len(data) == 1 and len(columns) == 1:
        return {"chart_type": "metric", "x_axis": None, "y_axis": columns[0], "explanation": "Single metric value."}

    prompt = f"""You are a Data Visualisation expert.
Return ONLY a raw JSON object (no markdown, no code fences) with these exact keys:
- chart_type: "bar" | "line" | "pie" | "metric" | "none"
- x_axis: column name for x-axis (null for metric/none)
- y_axis: column name for y-axis / numeric value (null for metric/none)
- explanation: one-sentence reason

Selection rules:
1. "line"   -> time-series data (date/month/year column on x-axis)
2. "bar"    -> category comparison (text labels on x-axis)
3. "pie"    -> part-of-whole with fewer than 7 categories
4. "metric" -> single-row single-numeric result
5. "none"   -> complex multi-column tables or text-only data

Columns: {columns}
Sample rows (up to 3): {data[:3]}

JSON:"""

    try:
        model = _get_model(api_key, temperature=0.0)
        response = model.generate_content(prompt)
        raw = response.text.strip()

        for fence in ("```json", "```"):
            if raw.startswith(fence):
                raw = raw[len(fence):]
        if raw.endswith("```"):
            raw = raw[:-3]
        return json.loads(raw.strip())
    except Exception:
        # Fallback: auto-detect chart type from columns
        num_cols = [c for c in columns if any(x in c.lower() for x in ["amount", "total", "count", "price", "qty", "revenue", "sales", "pct", "value"])]
        cat_cols = [c for c in columns if c not in num_cols]
        if cat_cols and num_cols:
            time_keywords = ["month", "date", "year", "week", "period"]
            if any(k in cat_cols[0].lower() for k in time_keywords):
                return {"chart_type": "line", "x_axis": cat_cols[0], "y_axis": num_cols[0], "explanation": "Time series detected."}
            return {"chart_type": "bar", "x_axis": cat_cols[0], "y_axis": num_cols[0], "explanation": "Category comparison."}
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "Could not determine chart type."}
