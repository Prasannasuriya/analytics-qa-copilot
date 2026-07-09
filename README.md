# 📊 Analytics Q&A Copilot (PRJ-029)

**Student:** PRASANNASURIYA.A.D | PSVPEC  
**Project Code:** PRJ-029  
**Tech Stack:** Python · FastAPI · LangChain · Gemini AI · FAISS · Streamlit · SQLite

---

## 🚀 Live Demo

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://analytics-app-copilot-j2cbkdcfnzfmtgzl73dqhm.streamlit.app/)

🔗 **Live App:** https://analytics-app-copilot-j2cbkdcfnzfmtgzl73dqhm.streamlit.app/  
📁 **GitHub Repo:** https://github.com/Prasannasuriya/analytics-qa-copilot

---

## 📌 Project Description

Analytics Q&A Copilot is a natural-language analytics assistant that lets users query operational dashboards and business reports by typing plain-English questions.  
It generates safe, schema-aware SQL queries, executes them, explains results in plain English, and recommends the best chart visualisation — all powered by **Google Gemini AI + LangChain + FAISS**.

---

## ✅ Required Features Implemented

| # | Feature | Status |
|---|---------|--------|
| 1 | **Schema-aware SQL generation** via LangChain + Gemini | ✅ Done |
| 2 | **Safe query execution** (SELECT-only guardrails, no destructive SQL allowed) | ✅ Done |
| 3 | **Plain-English result explanation** using Gemini LLM | ✅ Done |
| 4 | **Saved questions / prompt library** (persisted to JSON) | ✅ Done |
| 5 | **Chart recommendation** (bar / line / pie / metric via Altair) | ✅ Done |
| 6 | **Knowledge base upload** (FAISS vector store + document citations) | ✅ Done |
| 7 | **Custom SQLite DB upload** (bring your own database) | ✅ Done |

---

## 🏗️ Architecture

```
analytics-qa-copilot/
├── backend/
│   ├── main.py           # FastAPI REST API (7 endpoints)
│   ├── database.py       # SQLite init, schema extraction, safe query executor
│   ├── vector_store.py   # FAISS knowledge base (LangChain + Gemini embeddings)
│   └── copilot.py        # LangChain chains: SQL generation, explanation, chart recommendation
├── frontend/
│   ├── app.py            # Streamlit UI (standalone + API mode)
│   └── styles.css        # Custom dark-theme CSS
├── data/
│   ├── business_glossary.txt    # Sample knowledge-base document
│   └── query_guidelines.md      # SQL query pattern guide
├── tests/
│   └── test_backend.py   # Pytest unit tests
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

## 📂 Input Files Supported

### 1. 🗄️ Custom SQLite Database
Upload any `.db`, `.sqlite`, or `.sqlite3` file via the **Database** section in the sidebar.  
The app will auto-read the schema and generate SQL queries accordingly.

**Supported formats:**
```
sales_data.db
inventory.sqlite
company_reports.sqlite3
```

**Requirements:**
- Must be a valid SQLite database file
- Can have any number of tables and columns
- App auto-detects all table structures and relationships

---

### 2. 📚 Knowledge Base Documents
Upload `.txt` or `.md` files via the **Knowledge Base** section in the sidebar.  
These are chunked, embedded using FAISS + Gemini, and used as context for better SQL generation with source citations.

**What to include in these files:**

| Content Type | Example |
|---|---|
| Business term definitions | `"VIP Customer = total orders > $10,000"` |
| Column name explanations | `` "`total_amount` = order grand total including tax" `` |
| KPI formulas | `"Attainment % = (Actual Sales / Target) × 100"` |
| Date conventions | `"Fiscal year Jan–Dec, dates stored as YYYY-MM-DD"` |
| SQL JOIN relationships | `"orders.customer_id links to customers.id"` |
| Query pattern templates | Sample SQL for common business questions |

**Sample files provided in `/data/` folder:**
| File | Contents |
|---|---|
| `data/business_glossary.txt` | Customer segments, inventory terms, order statuses, KPI definitions |
| `data/query_guidelines.md` | SQL JOIN patterns, date handling rules, common query templates |

---

## 💬 Sample Questions to Try

### 📊 Sales Analysis
| Question | Chart Type |
|---|---|
| List the top 5 customers by total order amount | Bar chart |
| Show total sales category-wise for each month in 2025 | Line chart |
| What is the total revenue for Q1 2025? | Metric card |
| Which category generates the highest revenue? | Bar chart |

### 📈 Performance vs Targets
| Question | Chart Type |
|---|---|
| Compare total sales against the target for each category in March 2025 | Bar chart |
| Which categories missed their sales target in 2025? | Table |
| Show monthly sales trend for Electronics in 2025 | Line chart |

### 🛒 Orders & Operations
| Question | Chart Type |
|---|---|
| How many orders were cancelled and what was their total value? | Metric card |
| What is the average order value per customer? | Metric card |
| Show all orders placed in June 2025 | Table |
| Which products have the most returns? | Bar chart |

### 📦 Inventory Management
| Question | Chart Type |
|---|---|
| Show products that have less than 50 units in stock | Table |
| Which products are out of stock? | Table |
| List the top 10 best-selling products by quantity | Bar chart |
| Show inventory value by category | Pie chart |

### 👥 Customer Insights
| Question | Chart Type |
|---|---|
| Who are the VIP customers? | Table |
| How many new customers joined each month in 2025? | Line chart |
| Which city has the most customers? | Bar chart |

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

1. Push code to GitHub ✅ (already done)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select repo: `Prasannasuriya/analytics-qa-copilot`
4. Set **Main file path**: `frontend/app.py`
5. Go to **Settings → Secrets** and add:
```toml
GOOGLE_API_KEY = "your-gemini-api-key-here"
```
6. Click **Deploy** ✅

---

## 🗄️ Sample Database Schema

The app auto-generates a realistic business SQLite database with:

| Table | Records | Description |
|---|---|---|
| `customers` | 50 | Customer profiles with name, email, city |
| `products` | 30 | Products with price, stock, category |
| `categories` | 5 | Electronics, Clothing, Home & Garden, Sports, Books |
| `orders` | 200 | Orders with date, status, total amount |
| `order_items` | 400+ | Line items linking orders to products |
| `sales_targets` | 60 | Monthly targets per category (2024–2025) |

---

## 🔗 API Endpoints (FastAPI Backend)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | Get active database schema |
| POST | `/api/query` | Natural language → SQL → Results → Explanation |
| GET | `/api/saved-questions` | Get saved question library |
| POST | `/api/save-question` | Save a custom question |
| POST | `/api/upload-doc` | Upload knowledge base document |
| POST | `/api/reset-knowledge` | Clear knowledge base index |

---

## 🧪 Running Tests

```bash
pytest tests/test_backend.py -v
```

---
