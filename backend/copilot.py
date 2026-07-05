"""
Analytics Q&A Copilot — LLM pipeline
Uses google-genai SDK with v1 API + multiple model fallbacks.
The AQ. key format requires v1 API (not v1beta).
"""
import json
import time

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_NEW_SDK = True
except ImportError:
    HAS_NEW_SDK = False

try:
    import google.generativeai as old_genai
    HAS_OLD_SDK = True
except ImportError:
    HAS_OLD_SDK = False

# Models to try in order (working models first based on user API key capabilities)
MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-2.0-flash",
]


def _generate(prompt: str, api_key: str, temperature: float = 0.0) -> str:
    """Call Gemini trying v1 API first, then v1beta, across multiple models."""
    errors = []

    if HAS_NEW_SDK:
        # Try v1 API (works with AQ. keys)
        for model in MODELS:
            for api_ver in ["v1", "v1beta", "v1alpha"]:
                try:
                    client = genai.Client(
                        api_key=api_key,
                        http_options={"api_version": api_ver}
                    )
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(
                            temperature=temperature,
                            max_output_tokens=1024,
                        ),
                    )
                    return response.text.strip()
                except Exception as e:
                    err_str = str(e)
                    errors.append(f"[new/{api_ver}/{model}] {err_str[:80]}")
                    # If quota exhausted, try next model not next version
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        break
                    # If 404/not found, try next version
                    continue

    # Fallback: old SDK
    if HAS_OLD_SDK:
        for model in MODELS:
            try:
                old_genai.configure(api_key=api_key)
                m = old_genai.GenerativeModel(model)
                response = m.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                errors.append(f"[old/{model}] {str(e)[:80]}")

    raise RuntimeError(
        "All Gemini model attempts failed. Errors:\n" + "\n".join(errors[-6:])
    )


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
            "Database schema is empty — database is still initializing. "
            "Please wait a moment and try again."
        )
    if not user_query or not user_query.strip():
        raise ValueError("Question is empty.")

    context_str = ""
    if context_docs:
        context_str = "\nRelevant Domain Knowledge:\n"
        for i, doc in enumerate(context_docs):
            context_str += f"[{i+1}] {doc.get('content','')}\n"

    prompt = f"""You are a SQLite expert. Write ONE valid SQLite SELECT query.

Database Schema:
{db_schema}
{context_str}
Rules:
- Output ONLY raw SQL, no markdown, no explanation.
- Only SELECT statements. No INSERT/UPDATE/DELETE/DROP.
- Use strftime() for dates, not EXTRACT() or TO_DATE().
- Alias all aggregates: SUM(x) AS total.
- Match exact column and status values from schema.

Question: {user_query}
SQL:"""

    sql = _generate(prompt, api_key, temperature=0.0)
    return _strip_fences(sql)


def explain_results(user_query: str, sql_query: str, query_results: dict, api_key: str) -> str:
    """Plain-English summary of query results."""
    if not user_query or not api_key:
        return "Results retrieved successfully."

    data = query_results.get("data", [])
    if not data:
        return "The query returned no results for the given criteria."

    results_str = json.dumps(data[:10], indent=2)
    prompt = f"""Summarize these SQL query results in plain English (max 100 words).
Highlight key numbers, trends, or insights.

Question: {user_query}
Results: {results_str}

Summary:"""

    try:
        return _generate(prompt, api_key, temperature=0.2)
    except Exception:
        # If explanation fails, return a simple summary from data
        cols = query_results.get("columns", [])
        rows = query_results.get("row_count", len(data))
        return f"Query returned {rows} row(s). Columns: {', '.join(cols)}."


def recommend_chart(columns: list, data: list, api_key: str) -> dict:
    """Auto-detect best chart type without calling LLM (saves API quota)."""
    if not data or not columns:
        return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "No data."}
    if len(data) == 1 and len(columns) == 1:
        return {"chart_type": "metric", "x_axis": None, "y_axis": columns[0], "explanation": "Single value."}

    # Auto-detect without LLM call
    num_cols = [c for c in columns if any(x in c.lower() for x in
                ["amount", "total", "count", "price", "qty", "revenue",
                 "sales", "pct", "value", "stock", "spend", "target"])]
    cat_cols  = [c for c in columns if c not in num_cols]
    time_kw   = ["month", "date", "year", "week", "period", "day"]

    if len(data) == 1 and num_cols:
        return {"chart_type": "metric", "x_axis": None, "y_axis": num_cols[0], "explanation": "Single metric."}
    if cat_cols and num_cols:
        if any(k in cat_cols[0].lower() for k in time_kw):
            return {"chart_type": "line", "x_axis": cat_cols[0], "y_axis": num_cols[0], "explanation": "Time series."}
        if len(data) <= 6:
            return {"chart_type": "pie", "x_axis": cat_cols[0], "y_axis": num_cols[0], "explanation": "Part-of-whole."}
        return {"chart_type": "bar", "x_axis": cat_cols[0], "y_axis": num_cols[0], "explanation": "Category comparison."}
    return {"chart_type": "none", "x_axis": None, "y_axis": None, "explanation": "Table view."}
