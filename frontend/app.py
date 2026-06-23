import streamlit as st
import requests
import pandas as pd
import os
import json
import altair as alt

# Page Configuration
st.set_page_config(
    page_title="Analytics Q&A Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Backend API URL
API_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

# Load Custom Stylesheet
styles_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(styles_path):
    with open(styles_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_key" not in st.session_state:
    # Try reading from environment variable first
    st.session_state.api_key = os.environ.get("GOOGLE_API_KEY", "")
if "db_path" not in st.session_state:
    st.session_state.db_path = None
if "selected_question" not in st.session_state:
    st.session_state.selected_question = None

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
        
    st.markdown("<hr class='custom-hr'/>", unsafe_allow_html=True)
    
    # 2. Custom Database Upload
    st.markdown("### 🗄️ Database Settings")
    uploaded_db = st.file_uploader(
        "Connect Custom SQLite DB",
        type=["db", "sqlite", "sqlite3"],
        help="Upload a custom SQLite database file to query your own schema."
    )
    
    if uploaded_db is not None:
        # Save custom DB locally
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        os.makedirs(upload_dir, exist_ok=True)
        custom_db_path = os.path.join(upload_dir, "uploaded_database.db")
        
        with open(custom_db_path, "wb") as f:
            f.write(uploaded_db.getbuffer())
            
        if st.session_state.db_path != custom_db_path:
            st.session_state.db_path = custom_db_path
            st.success(f"Connected to: {uploaded_db.name}")
            st.session_state.messages = []  # Clear history on DB change
            st.rerun()
            
    # Reset Database button if custom DB is connected
    if st.session_state.db_path is not None:
        if st.button("Reset to Default Sample DB"):
            st.session_state.db_path = None
            st.success("Reset to sample database.")
            st.session_state.messages = []
            st.rerun()

    st.markdown("<hr class='custom-hr'/>", unsafe_allow_html=True)

    # 3. Knowledge Base / Domain Docs Upload
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
                try:
                    files = {"file": (uploaded_doc.name, uploaded_doc.getvalue(), "text/plain")}
                    data = {"api_key": st.session_state.api_key}
                    response = requests.post(f"{API_URL}/api/upload-doc", files=files, data=data)
                    
                    if response.status_code == 200:
                        st.success(response.json()["message"])
                    else:
                        st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Failed to connect to backend: {e}")
                    
    if st.button("Clear Knowledge Base", help="Resets the indexed documents in vector store"):
        try:
            response = requests.post(f"{API_URL}/api/reset-knowledge")
            if response.status_code == 200:
                st.success("Vector store reset complete.")
            else:
                st.error("Failed to reset vector store.")
        except Exception as e:
            st.error(f"Connection error: {e}")

# Header Area
st.markdown("<div class='title-gradient'>Analytics Q&A Copilot</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle-text'>Natural-language database explorer powered by Gemini & FastAPI</div>", unsafe_allow_html=True)

# Main Application Layout - Tabs
tab_chat, tab_schema = st.tabs(["💬 Assistant Chat", "🗂️ Database Schema"])

# 1. Fetch Schema Details
schema_info = None
backend_online = False
try:
    params = {}
    if st.session_state.db_path:
        params["db_path"] = st.session_state.db_path
    schema_res = requests.get(f"{API_URL}/api/schema", params=params)
    if schema_res.status_code == 200:
        schema_info = schema_res.json()
        backend_online = True
except Exception:
    backend_online = False

# Render Database Schema Tab
with tab_schema:
    if not backend_online:
        st.error("🔴 Backend API server is offline. Please start the FastAPI backend server first.")
    elif schema_info:
        st.markdown(f"**Connected Database File:** `{schema_info.get('db_path')}`")
        
        # Display statistics / metrics
        schema_text = schema_info.get("schema", "")
        # Parse schema tables
        tables = [line.split("Table: ")[1] for line in schema_text.split("\n") if line.startswith("Table: ")]
        
        # Metric layout
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
        
        # Display Schema Code
        st.markdown("### Schema Structure")
        st.code(schema_text, language="text")

# Render Assistant Chat Tab
with tab_chat:
    if not backend_online:
        st.error("🔴 Backend API server is offline. Please run: `uvicorn backend.main:app --port 8000` to start the backend service.")
    
    # 1. Saved / Quick Questions Grid
    st.markdown("##### 💡 Suggested Questions")
    try:
        q_res = requests.get(f"{API_URL}/api/saved-questions")
        if q_res.status_code == 200:
            saved_qs = q_res.json()
            
            # Display quick options in columns
            cols = st.columns(len(saved_qs))
            for idx, q_item in enumerate(saved_qs):
                with cols[idx]:
                    if st.button(q_item["question"], key=f"sq_{idx}", help=q_item.get("description", "")):
                        st.session_state.selected_question = q_item["question"]
                        st.rerun()
    except Exception as e:
        st.warning("Failed to load saved questions from backend.")

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
                        # Format if float
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

    # 4. Handle Selected Quick Question or Chat Input
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
            
            # Query backend
            with st.spinner("Analyzing schema, generating query and fetching results..."):
                try:
                    headers = {"X-API-Key": st.session_state.api_key}
                    payload = {"query": prompt}
                    if st.session_state.db_path:
                        payload["db_path"] = st.session_state.db_path
                        
                    response = requests.post(f"{API_URL}/api/query", headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        res_json = response.json()
                        if res_json.get("success", False):
                            st.session_state.messages.append({"role": "assistant", "content": res_json})
                            # Save custom question automatically to the saved questions list
                            requests.post(f"{API_URL}/api/saved-questions", json={
                                "question": prompt,
                                "description": f"User question: {prompt}",
                                "category": "Custom"
                            })
                        else:
                            # Returned SQL error or safety block
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
                                "explanation": f"💥 Server Error ({response.status_code}): {response.text}",
                                "query": "",
                                "data": [],
                                "chart": {"chart_type": "none"}
                            }
                        })
                except Exception as e:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": {
                            "explanation": f"🔌 Failed to communicate with FastAPI server. Is it running? Error: {e}",
                            "query": "",
                            "data": [],
                            "chart": {"chart_type": "none"}
                        }
                    })
            st.rerun()
