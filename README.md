# 📊 Analytics Q&A Copilot (PRJ-029)

**Student:** PRASANNASURIYA.A.D | PSVPEC  
**Project Code:** PRJ-029  
**Tech Stack:** Python · FastAPI · LangChain · Gemini AI · FAISS · Streamlit · SQLite

---

## 🚀 Live Demo
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://analytics-qa-copilot.streamlit.app)

---

## 📌 Project Description
Analytics Q&A Copilot is a natural-language analytics assistant that lets users query operational dashboards and business reports by typing plain English questions.  
It generates safe, schema-aware SQL queries, executes them, explains results in plain English, and recommends the best chart visualisation — all powered by Google Gemini AI.

---

## ✅ Required Features Implemented

| # | Feature | Status |
|---|---------|--------|
| 1 | **Schema-aware SQL generation** via LangChain + Gemini | ✅ Done |
| 2 | **Safe query execution** (SELECT-only guardrails, no destructive SQL) | ✅ Done |
| 3 | **Plain-English result explanation** using Gemini LLM | ✅ Done |
| 4 | **Saved questions / prompt library** (persisted to JSON) | ✅ Done |
| 5 | **Chart recommendation** (bar / line / pie / metric via Altair) | ✅ Done |
| 6 | **Knowledge base upload** (FAISS vector store + citations) | ✅ Done |
| 7 | **Custom SQLite DB upload** (bring your own database) | ✅ Done |

---

## 🏗️ Architecture

```
analytics-qa-copilot/
├── backend/
│   ├── main.py          # FastAPI REST API (7 endpoints)
│   ├── database.py      # SQLite init, schema extraction, safe query executor
│   ├── vector_store.py  # FAISS knowledge base (LangChain + Gemini embeddings)
│   └── copilot.py       # LangChain chains: SQL gen, explanation, chart recommendation
├── frontend/
│   ├── app.py           # Streamlit UI (standalone + API mode)
│   └── styles.css       # Custom dark-theme CSS
├── data/
│   ├── business_glossary.txt   # Sample knowledge-base document
│   └── query_guidelines.md     # SQL query pattern guide
├── tests/
│   └── test_backend.py  # Pytest unit tests
├── requirements.txt
└── .streamlit/
    └── config.toml
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 1.5 Flash (via `langchain-google-genai`) |
| Orchestration | LangChain (chains, prompts, output parsers) |
| Vector Store | FAISS (local, via `faiss-cpu`) |
| Embeddings | Google `text-embedding-004` |
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Database | SQLite (via SQLAlchemy) |
| Charts | Altair |

---

## 🖥️ How to Run Locally

### 1. Clone the repo
```bash
git clone https://github.com/Prasannasuriya/analytics-qa-copilot.git
cd analytics-qa-copilot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your Gemini API Key
Create `.streamlit/secrets.toml`:
```toml
GOOGLE_API_KEY = "your-gemini-api-key-here"
```
Get a free key at: https://aistudio.google.com/app/apikey

### 4. Start the FastAPI backend
```bash
uvicorn backend.main:app --port 8000
```

### 5. Start the Streamlit frontend (new terminal)
```bash
streamlit run frontend/app.py
```

### 6. Open in browser
```
http://localhost:8501
```

---

## 🌐 Deploying to Streamlit Cloud

1. Push code to GitHub (already done ✅)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Set **Main file path**: `frontend/app.py`
4. Go to **Settings → Secrets** and add:
```toml
GOOGLE_API_KEY = "your-gemini-api-key-here"
```
5. Click **Deploy**

---

## 🗄️ Sample Database Schema

The app auto-generates a realistic business SQLite database with:
- `customers` — 50 customer records
- `products` — 30 products across 5 categories
- `categories` — Electronics, Clothing, Home & Garden, Sports, Books
- `orders` — 200 orders with statuses (delivered, shipped, cancelled, returned)
- `order_items` — Line items linking orders to products
- `sales_targets` — Monthly targets per category for 2024–2025

---

## 💬 Sample Questions to Try

- *"List the top 5 customers by total order amount"*
- *"Show total sales category-wise for each month in 2025"*
- *"How many orders were cancelled and what was their total value?"*
- *"Compare total sales against the target for each category in March 2025"*
- *"Show products that have less than 50 units in stock"*

---

## 🧪 Running Tests

```bash
pytest tests/test_backend.py -v
```

---

## 📄 License
This project is submitted as an individual academic project under PSVPEC.
