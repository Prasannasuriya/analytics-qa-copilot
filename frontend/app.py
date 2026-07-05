import os, sys, json
import streamlit as st
import requests
import pandas as pd
import altair as alt

# ── Project root on sys.path so "backend" package is importable ──────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Try importing backend (standalone / cloud mode) ──────────────────────────
try:
    from backend.database import init_database, get_db_schema, execute_safe_query
    from backend.vector_store import SchemaKnowledgeBase
    from backend.copilot import generate_sql, explain_results, recommend_chart
    HAS_BACKEND = True
except Exception:
    HAS_BACKEND = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Analytics Q&A Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
css_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Resolve data directory (writable on both local & cloud) ──────────────────
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
if not os.access(PROJECT_ROOT, os.W_OK):          # cloud: use /tmp
    DATA_DIR = "/tmp/analytics_copilot_data"
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_DB   = os.path.join(DATA_DIR, "sample_business.db")
FAISS_DIR    = os.path.join(DATA_DIR, "faiss_index")
SAVED_Q_FILE = os.path.join(DATA_DIR, "saved_questions.json")

# Initialise the vector store (singleton per session)
if HAS_BACKEND:
    vector_kb = SchemaKnowledgeBase(index_dir=FAISS_DIR)

# ── API URL for FastAPI backend (local dev) ────────────────────────────────────
API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"          not in st.session_state: st.session_state.messages          = []
if "db_path"           not in st.session_state: st.session_state.db_path           = None
if "selected_question" not in st.session_state: st.session_state.selected_question = None

# ── Auto-load API key from Streamlit Secrets → env → empty ───────────────────
if "api_key" not in st.session_state:
    key = ""
    try:
        key = st.secrets.get("GOOGLE_API_KEY", "") or st.secrets.get("general", {}).get("GOOGLE_API_KEY", "")
    except Exception:
        pass
    if not key:
        key = os.environ.get("GOOGLE_API_KEY", "")
    st.session_state.api_key = key

# ── Saved-questions helpers ───────────────────────────────────────────────────
DEFAULT_QUESTIONS = [
    {"question": "List the top 5 customers by total order amount.",                             "category": "Sales",       "description": "Highest-value customers ranked by spend."},
    {"question": "Show total sales category-wise for each month in 2025.",                      "category": "Trends",      "description": "Monthly revenue broken down by product category."},
    {"question": "How many orders were cancelled and what was their total value?",              "category": "Operations",  "description": "Cancellation count and lost revenue."},
    {"question": "Compare total sales against the target for each category in March 2025.",    "category": "Performance", "description": "Actual vs target revenue by category."},
    {"question": "Show products that have less than 50 units in stock.",                        "category": "Inventory",   "description": "Low-stock product alert list."},
]

def load_questions() -> list:
    if os.path.exists(SAVED_Q_FILE):
        try:
            return json.load(open(SAVED_Q_FILE))
        except Exception:
            pass
    json.dump(DEFAULT_QUESTIONS, open(SAVED_Q_FILE, "w"), indent=2)
    return DEFAULT_QUESTIONS

def save_question(q: dict):
    qs = load_questions()
    if not any(x["question"].lower() == q["question"].lower() for x in qs):
        qs.append(q)
        json.dump(qs, open(SAVED_Q_FILE, "w"), indent=2)

# ── Detect whether the local FastAPI backend is reachable ─────────────────────
def backend_alive() -> bool:
    try:
        r = requests.get(f"{API_URL}/api/health", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False

BACKEND_UP = backend_alive()

# ═════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    # ── Gemini API Key ────────────────────────────────────────────────────────
    new_key = st.text_input(
        "🔑 Gemini API Key",
        value=st.session_state.api_key,
        type="password",
        help="Get a free key at https://aistudio.google.com/",
    )
    if new_key != st.session_state.api_key:
        st.session_state.api_key = new_key
        st.session_state.messages = []
        st.rerun()

    if st.session_state.api_key:
        st.success("API Key loaded ✅")
    else:
        st.warning("⚠️ Enter your Gemini API Key above to start.")

    st.divider()

    # ── Custom SQLite DB upload ───────────────────────────────────────────────
    st.markdown("### 🗄️ Database")
    st.caption("Default sample DB is loaded automatically. Upload your own SQLite file to query custom data.")
    db_file = st.file_uploader("Upload SQLite DB", type=["db", "sqlite", "sqlite3"])
    if db_file:
        custom_path = os.path.join(DATA_DIR, "uploaded.db")
        with open(custom_path, "wb") as fh:
            fh.write(db_file.getbuffer())
        if st.session_state.db_path != custom_path:
            st.session_state.db_path = custom_path
            st.session_state.messages = []
            st.success(f"Connected: {db_file.name}")
            st.rerun()

    if st.session_state.db_path:
        if st.button("↩ Reset to default sample DB"):
            st.session_state.db_path = None
            st.session_state.messages = []
            st.rerun()

    st.divider()

    # ── Knowledge-base document upload ───────────────────────────────────────
    st.markdown("### 📚 Knowledge Base")
    st.caption("Upload a `.txt` or `.md` glossary / data-dictionary to improve query accuracy.")
    doc_file = st.file_uploader("Upload guide / glossary", type=["txt", "md"])
    if doc_file:
        with st.spinner("Indexing document…"):
            done = False
            if BACKEND_UP:
                try:
                    r = requests.post(
                        f"{API_URL}/api/upload-doc",
                        files={"file": (doc_file.name, doc_file.getvalue(), "text/plain")},
                        data={"api_key": st.session_state.api_key or "none"},
                    )
                    if r.status_code == 200:
                        st.success(r.json().get("message", "Indexed ✅"))
                        done = True
                except Exception:
                    pass
            if not done and HAS_BACKEND:
                try:
                    vector_kb.add_document(
                        text_content=doc_file.getvalue().decode("utf-8", errors="ignore"),
                        source_name=doc_file.name,
                        api_key=st.session_state.api_key or "none",
                    )
                    st.success(f"✅ '{doc_file.name}' indexed successfully!")
                    done = True
                except Exception:
                    pass
            if not done:
                # Store as plain text in session state as final fallback
                kb_key = f"kb_{doc_file.name}"
                st.session_state[kb_key] = doc_file.getvalue().decode("utf-8", errors="ignore")
                st.success(f"✅ '{doc_file.name}' saved as context!")

    if st.button("🗑 Clear knowledge base"):
        done = False
        if BACKEND_UP:
            try:
                r = requests.post(f"{API_URL}/api/reset-knowledge")
                if r.status_code == 200:
                    st.success("Knowledge base cleared.")
                    done = True
            except Exception:
                pass
        if not done and HAS_BACKEND:
            vector_kb.reset()
            st.success("Knowledge base cleared (standalone).")

    st.divider()
    st.caption(f"**Backend:** {'🟢 Online' if BACKEND_UP else '🟡 Standalone mode'}")

# ═════════════════════════════════════════════════════════════════════════════
#  MAIN CONTENT
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='title-gradient'>Analytics Q&A Copilot</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle-text'>Natural-language analytics assistant powered by Gemini · FastAPI · LangChain · FAISS</div>", unsafe_allow_html=True)

tab_chat, tab_schema = st.tabs(["💬 Assistant Chat", "🗂️ Database Schema"])

# ── Active DB path & schema ───────────────────────────────────────────────────
active_db = st.session_state.db_path or DEFAULT_DB

# Cache schema in session state keyed by DB path so we don't re-init every rerun
schema_cache_key = f"schema_{active_db}"
if schema_cache_key not in st.session_state:
    schema_text = ""
    # 1. Try FastAPI backend
    if BACKEND_UP:
        try:
            params = {"db_path": active_db} if st.session_state.db_path else {}
            schema_text = requests.get(f"{API_URL}/api/schema", params=params, timeout=3).json().get("schema", "")
        except Exception:
            pass
    # 2. Standalone: always init DB first then read schema
    if not schema_text and HAS_BACKEND:
        try:
            init_database(active_db)
            schema_text = get_db_schema(active_db)
        except Exception as e:
            schema_text = ""
            st.error(f"Database init failed: {e}")
    st.session_state[schema_cache_key] = schema_text

schema_text = st.session_state.get(schema_cache_key, "")

# ── Schema tab ────────────────────────────────────────────────────────────────
with tab_schema:
    tables = [l.split("Table: ")[1] for l in schema_text.splitlines() if l.startswith("Table: ")]
    st.markdown(f"""
    <div class='metric-container'>
      <div class='metric-card'><h3>Engine</h3><p>SQLite</p></div>
      <div class='metric-card'><h3>Tables</h3><p>{len(tables)}</p></div>
      <div class='metric-card'><h3>Status</h3><p style='color:#4ade80'>Connected</p></div>
      <div class='metric-card'><h3>Backend</h3><p style='color:{"#4ade80" if BACKEND_UP else "#facc15"}'>{"Online" if BACKEND_UP else "Standalone"}</p></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**Database:** `{active_db}`")
    st.code(schema_text, language="text")

# ── Chat tab ──────────────────────────────────────────────────────────────────
with tab_chat:

    # Saved / quick questions
    saved_qs = []
    if BACKEND_UP:
        try:
            saved_qs = requests.get(f"{API_URL}/api/saved-questions", timeout=2).json()
        except Exception:
            pass
    if not saved_qs:
        saved_qs = load_questions()

    st.markdown("##### 💡 Suggested Questions")
    cols = st.columns(len(saved_qs))
    for i, q in enumerate(saved_qs):
        if cols[i].button(q["question"], key=f"sq_{i}", help=q.get("description", "")):
            st.session_state.selected_question = q["question"]
            st.rerun()

    if not st.session_state.api_key:
        st.info("💡 Enter your Gemini API Key in the sidebar to begin.")

    st.markdown("<hr style='border-top:1px solid rgba(255,255,255,0.07);margin:1.2rem 0'/>", unsafe_allow_html=True)

    # ── Render chat history ───────────────────────────────────────────────────
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div style="display:flex;justify-content:flex-end;margin-bottom:.8rem">
              <div class="chat-bubble-user"><b>You:</b><br>{msg["content"]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            res = msg["content"]
            st.markdown(f"""
            <div style="display:flex;justify-content:flex-start;margin-bottom:.5rem">
              <div class="chat-bubble-assistant"><b>Assistant:</b><br>{res.get("explanation","—")}</div>
            </div>""", unsafe_allow_html=True)

            # Chart
            chart_cfg = res.get("chart", {})
            data      = res.get("data", [])
            if chart_cfg and chart_cfg.get("chart_type") not in ("none", None) and data:
                df    = pd.DataFrame(data)
                x_col = chart_cfg.get("x_axis")
                y_col = chart_cfg.get("y_axis")
                ctype = chart_cfg.get("chart_type")

                if ctype == "metric" and y_col and y_col in df.columns:
                    val = df[y_col].iloc[0]
                    st.metric(label=y_col, value=f"${val:,.2f}" if isinstance(val, float) else f"{val:,}")

                elif ctype == "bar" and x_col in df.columns and y_col in df.columns:
                    st.altair_chart(
                        alt.Chart(df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#4D96FF")
                        .encode(x=alt.X(x_col, sort=None), y=alt.Y(y_col), tooltip=list(df.columns))
                        .properties(height=320).configure_view(strokeWidth=0),
                        use_container_width=True,
                    )

                elif ctype == "line" and x_col in df.columns and y_col in df.columns:
                    st.altair_chart(
                        alt.Chart(df).mark_line(point=True, color="#FF6B6B", strokeWidth=3)
                        .encode(x=alt.X(x_col, sort=None), y=alt.Y(y_col), tooltip=list(df.columns))
                        .properties(height=320),
                        use_container_width=True,
                    )

                elif ctype == "pie" and x_col in df.columns and y_col in df.columns:
                    st.altair_chart(
                        alt.Chart(df).mark_arc(innerRadius=48)
                        .encode(
                            theta=alt.Theta(field=y_col, type="quantitative"),
                            color=alt.Color(field=x_col, type="nominal", scale=alt.Scale(scheme="category10")),
                            tooltip=list(df.columns),
                        ).properties(height=300),
                        use_container_width=True,
                    )

            # SQL + raw data expander
            with st.expander("🔍 View generated SQL & raw data"):
                st.code(res.get("query", ""), language="sql")
                if data:
                    st.dataframe(pd.DataFrame(data), use_container_width=True)
                else:
                    st.warning("No rows returned.")

            # Citations
            for cit in res.get("citations", []):
                st.markdown(f"""<div class="citation-box">
                  <b>📚 Source:</b> {cit.get("source","?")} &nbsp;—&nbsp; {cit.get("content","")}
                </div>""", unsafe_allow_html=True)

            st.markdown("<hr style='border-top:1px solid rgba(255,255,255,0.05);margin:1.2rem 0'/>", unsafe_allow_html=True)

    # ── Prompt input ──────────────────────────────────────────────────────────
    prompt = None
    if st.session_state.selected_question:
        prompt = st.session_state.selected_question
        st.session_state.selected_question = None
    else:
        inp = st.chat_input("Ask anything about your data…")
        if inp and inp.strip():
            prompt = inp.strip()

    if prompt:
        if not st.session_state.api_key:
            st.error("⚠️ Please enter your Gemini API Key in the sidebar first.")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": prompt})
        result = {}

        with st.spinner("Generating query and fetching results…"):

            # ── Try FastAPI backend first ─────────────────────────────────────
            if BACKEND_UP:
                try:
                    r = requests.post(
                        f"{API_URL}/api/query",
                        headers={"X-API-Key": st.session_state.api_key},
                        json={"query": prompt, **({"db_path": active_db} if st.session_state.db_path else {})},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        result = r.json()
                except Exception:
                    pass

            # ── Standalone fallback ───────────────────────────────────────────
            if not result and HAS_BACKEND:
                try:
                    # Ensure schema is available - re-init if empty
                    current_schema = schema_text
                    if not current_schema.strip():
                        try:
                            init_database(active_db)
                            current_schema = get_db_schema(active_db)
                            st.session_state[schema_cache_key] = current_schema
                        except Exception:
                            pass

                    if not current_schema.strip():
                        result = {"success": False, "error": "Could not load database schema. Please refresh the page.", "query": "", "data": [], "citations": []}
                    else:
                        citations = []
                        try:
                            citations = vector_kb.search(prompt, api_key=st.session_state.api_key, k=2)
                        except Exception:
                            pass

                        sql = generate_sql(current_schema, prompt, citations, st.session_state.api_key)
                        exec_res = execute_safe_query(active_db, sql)

                        if not exec_res.get("success"):
                            result = {
                                "success": False,
                                "query": sql,
                                "error": exec_res.get("error", "Execution failed."),
                                "citations": citations,
                            }
                        else:
                            explanation = explain_results(prompt, sql, exec_res, st.session_state.api_key)
                            chart       = recommend_chart(exec_res["columns"], exec_res["data"], st.session_state.api_key)
                            result = {
                                "success":     True,
                                "query":       sql,
                                "columns":     exec_res["columns"],
                                "data":        exec_res["data"],
                                "row_count":   exec_res["row_count"],
                                "explanation": explanation,
                                "chart":       chart,
                                "citations":   citations,
                            }
                            save_question({"question": prompt, "category": "Custom", "description": ""})
                except Exception as e:
                    result = {"success": False, "error": str(e), "query": "", "data": [], "citations": []}

        # ── Append assistant message ──────────────────────────────────────────
        if result.get("success"):
            st.session_state.messages.append({"role": "assistant", "content": result})
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": {
                    "explanation": f"❌ {result.get('error', 'Unknown error')}",
                    "query": result.get("query", ""),
                    "data": [], "chart": {"chart_type": "none"}, "citations": result.get("citations", []),
                },
            })
        st.rerun()
