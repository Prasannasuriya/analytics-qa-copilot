# Analytics Q&A Copilot (PRJ-029)

A natural-language analytics assistant for operational dashboards and reports. The application allows users to ask questions in plain English, generates and safely executes schema-aware SQL queries on a database, visualizes results, and provides text-based explanations and citations from an indexed knowledge base.

---

## 🚀 Features

- **Schema-Aware Query Generation**: Generates syntactically correct SQLite queries by analyzing database table structures, columns, relationships, and custom metadata.
- **Safe SQL Execution Layer**: Intercepts queries before execution to ensure they are read-only (`SELECT`). Any write operation (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.) is blocked.
- **Result Explanation**: Translates tabular database outputs into clear, professional, business-focused text summaries.
- **Visualization Suggester**: Automatically determines the best chart type (bar, line, pie, metric, or table) based on the column types and returns appropriate data mappings.
- **Dynamic Charting**: Renders clean, modern, interactive charts directly in the UI.
- **Saved Prompts / Quick Questions**: Includes pre-saved operational questions and automatically saves successful user questions.
- **Document Knowledge Base**: Allows indexing custom files (e.g. data dictionaries, glossaries) into a `FAISS` vector store using Gemini Embeddings, which are retrieved and cited when relevant.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI + Uvicorn + Python 3.12
- **GenAI/LLM Framework**: LangChain + Google GenAI (Gemini 1.5 Flash)
- **Vector Database**: FAISS (for document index retrieval)
- **Database**: SQLite3
- **Frontend**: Streamlit + Altair (custom themed CSS layout)
- **Data Handling**: Pandas + SQLAlchemy

---

## 📂 Project Directory Structure

```
analytics-qa-copilot/
├── requirements.txt         # Project dependencies
├── test_copilot.py          # Unit & safety test suite
├── README.md                # System documentation
├── backend/                 # API Server & AI Chains
│   ├── __init__.py
│   ├── main.py              # FastAPI endpoints
│   ├── database.py          # SQLite connections & safety validations
│   ├── copilot.py           # SQL generation, explanation & charting chains
│   └── vector_store.py      # FAISS vector indexing & similarity search
├── frontend/                # Interactive Web UI
│   ├── app.py               # Streamlit application layout
│   └── styles.css           # Custom CSS styles (glassmorphism UI)
└── data/                    # Generated database & vector index (Auto-created)
    ├── sample_business.db   # SQLite sample data file
    ├── faiss_index/         # FAISS vector store binary files
    └── saved_questions.json # Predefined and custom saved questions list
```

---

## 💾 Database Schema

By default, the backend initializes a sample SQLite database containing realistic business operations data:
1. **`customers`**: `customer_id` (PK), `name`, `email`, `country`, `signup_date`
2. **`products`**: `product_id` (PK), `name`, `category`, `price`, `stock`
3. **`orders`**: `order_id` (PK), `customer_id` (FK), `order_date`, `total_amount`, `status`
4. **`order_items`**: `item_id` (PK), `order_id` (FK), `product_id` (FK), `quantity`, `price`
5. **`sales_targets`**: `target_id` (PK), `year`, `month`, `target_amount`, `category`

---

## 🔧 Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Gemini API Key (obtain from [Google AI Studio](https://aistudio.google.com/))

### 1. Install Dependencies
Navigate to the project root directory and run:
```bash
pip install -r requirements.txt
```

### 2. Start the Backend API
Run the FastAPI backend server using Uvicorn:
```bash
uvicorn backend.main:app --port 8000 --reload
```
The API documentation will be available at `http://localhost:8000/docs`.

### 3. Start the Frontend Dashboard
In a separate terminal, launch the Streamlit interface:
```bash
streamlit run frontend/app.py
```
This will open the application in your default web browser (usually at `http://localhost:8501`).

---

## 🧪 Testing

Run the automated test cases (verifying database creation, schema parsing, and SQL safety guards):
```bash
python test_copilot.py
```

---

## 📖 Usage Guide

1. **Setup Gemini Key**: Enter your Gemini API Key in the **Sidebar** text box.
2. **Check Schema**: Navigate to the **Database Schema** tab to inspect the connected SQLite database.
3. **Ask Questions**:
   - Click any of the **Suggested Questions** at the top of the interface.
   - Or, type a custom question in the chat input (e.g., *"Show the total sales for the product 'Standing Desk' month-by-month"*).
4. **View Outputs**:
   - **Assistant**: Plain-English explanation.
   - **Chart**: Generated visual representation (bar chart, line chart, or metric).
   - **SQL Details**: Expand to inspect the generated SQL query and the raw data table returned.
   - **Citations**: Shows relevant chunks pulled from uploaded documentation (if any).
5. **Enhance with Knowledge Base**: Upload custom data glossary text/markdown files to help the assistant map custom jargon (e.g. *"ROI"* or *"VIP Customer"*) to your specific columns.
