"""
Analytics Q&A Copilot — LLM pipeline
Uses google-genai (new unified SDK) which works with all Gemini API key formats.
"""
import json

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_NEW_SDK = True
except ImportError:
    HAS_NEW_SDK = False

# Fallback to old SDK
try:
    import google.generativeai as old_genai
    HAS_OLD_SDK = True
except ImportError:
    HAS_OLD_SDK = False

# Model priority list — tries each in order
MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]


def _generate(prompt: str, api_key: str, temperature: float = 0.0) -> str:
    """Call Gemini with the prompt, trying multiple SDK versions and model names."""
    errors = []

    # --- Try new google-genai SDK first ---
    if HAS_NEW_SDK:
        for model in MODELS:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(temperature=temperature),
                )
                return response.text.strip()
            except Exception as e:
                errors.append(f"[new-sdk/{model}] {e}")

    # --- Fallback to old google-generativeai SDK ---
    if HAS_OLD_SDK:
        for model in MODELS:
            try:
                old_genai.configure(api_key=api_key)
                m = old_genai.GenerativeModel(model)
                response = m.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                errors.append(f"[old-sdk/{model}] {e}")

    raise RuntimeError("All Gemini model attempts failed:\n" + "\n".join(errors))


def _strip_fences(text: str) -> str:
    for fence in ("```sql", "```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


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
            context_str += f"[{i+1}] (Source: {doc.get('source','?')}): {doc.get('content','')}\n"

    prompt = f"""You are a highly skilled SQL Analyst specialising in SQLite.
Write ONE clean, valid SQLite SELECT query to answer the user question.

Database Schema:
{db_schema}
{context_str}
Rules:
1. Output ONLY the raw SQL. No markdown fences, no explanation.
2. Only SELECT or WITH (CTE) — never INSERT/UPDATE/DELETE/DROP/ALTER.
3. Use only tables and columns listed in the schema.
4. For dates use strftime('%Y', col) — SQLite does NOT support EXTRACT or TO_DATE.
5. Always alias aggregates: SUM(o.total_amount) AS total_sales.
6. Match exact status values shown in schema (case-sensitive).

User Question: {user_query}
SQL Query:"""

    sql = _generate(prompt, api_key, temperature=0.0)
    return _strip_fences(sql)


def explain_results(user_query: str, sql_query: str, query_results: dict, api_key: str) -> str:
    """Translate raw tabular results into a plain-English business summary."""
    if not user_query or not api_key:
        return "Unable to generate explanation."

    data = query_results.get("data", [])
    results_str = json.dumps(data[:20], indent=2) if data else "No rows returned."

    prompt = f"""You are a Business Intelligence Analyst.
Explain the SQL results to a business user in plain English (max 150 words).
Highlight key insights: trends, totals, outliers, comparisons.
If results are empty, say so clearly.

User Question: {user_query}
SQL Executed: {sql_query}
Results (JSON): {results_str}

Explanation:"""

    try:
        return _generate(prompt, api_key, temperature=0.2)
    except Exception as e:
        return f"Could not generate explanation: {e}"


def recommend_chart(columns: list, data: list, api_key: str) -> dict:
    """Suggest the best Altair chart type and axis mapping for the result set."""
    if not data or not columns:
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "No data to chart."}
    if len(data) == 1 and len(columns) == 1:
        return {"chart_type": "metric", "x_axis": None, "y_axis": columns[0], "explanation": "Single metric value."}

    prompt = f"""You are a Data Visualisation expert.
Return ONLY a raw JSON object (no markdown, no code fences) with keys:
- chart_type: "bar" | "line" | "pie" | "metric" | "none"
- x_axis: column name for x-axis (null for metric/none)
- y_axis: column name for y-axis (null for metric/none)
- explanation: one-sentence reason

Rules:
1. "line"   -> time-series (month/date/year on x-axis)
2. "bar"    -> category comparison
3. "pie"    -> part-of-whole with fewer than 7 categories
4. "metric" -> single-row single-number
5. "none"   -> complex multi-column table

Columns: {columns}
Sample rows (up to 3): {data[:3]}

JSON:"""

    try:
        raw = _generate(prompt, api_key, temperature=0.0)
        return json.loads(_strip_fences(raw))
    except Exception:
        # Auto-detect fallback
        num_cols = [c for c in columns if any(x in c.lower() for x in
                    ["amount","total","count","price","qty","revenue","sales","pct","value","stock"])]
        cat_cols  = [c for c in columns if c not in num_cols]
        if cat_cols and num_cols:
            time_kw = ["month","date","year","week","period"]
            if any(k in cat_cols[0].lower() for k in time_kw):
                return {"chart_type":"line","x_axis":cat_cols[0],"y_axis":num_cols[0],"explanation":"Time series."}
            return {"chart_type":"bar","x_axis":cat_cols[0],"y_axis":num_cols[0],"explanation":"Category comparison."}
        return {"chart_type":"none","x_axis":None,"y_axis":None,"explanation":"Could not determine chart type."}
