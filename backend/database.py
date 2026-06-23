import os
import sqlite3
import re
import pandas as pd
from datetime import datetime, timedelta
import random

def init_database(db_path: str):
    """
    Initializes a sample SQLite database with realistic business tables
    and populated dummy data if the database file does not exist.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    # Force initialization if file size is 0 or doesn't exist
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        country TEXT NOT NULL,
        signup_date DATE NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        order_date DATE NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        price INTEGER NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales_targets (
        target_id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        target_amount REAL NOT NULL,
        category TEXT NOT NULL
    );
    """)

    # Populate Sample Data
    random.seed(42)
    
    # 1. Populate Customers
    countries = ["USA", "Canada", "UK", "Germany", "France", "Japan", "Australia", "India"]
    customer_names = [
        "Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Evan Wright", 
        "Fiona Gallagher", "George Clark", "Hannah Abbott", "Ian Malcolm", "Julia Roberts",
        "Kevin Bacon", "Laura Croft", "Michael Scott", "Nancy Drew", "Oliver Twist",
        "Penelope Cruz", "Quincy Adams", "Rachel Green", "Steve Rogers", "Tony Stark",
        "Uma Thurman", "Victor Stone", "Wanda Maximoff", "Xavier Charles", "Yolanda Adams",
        "Zachary Levi", "Arthur Pendragon", "Bruce Wayne", "Clark Kent", "David Miller",
        "Emma Watson", "Frank Sinatra", "Grace Hopper", "Harry Potter", "Iris West",
        "John Doe", "Katherine Pierce", "Leo Messi", "Mary Jane", "Nathan Drake"
    ]
    
    customers_data = []
    base_date = datetime(2025, 1, 1)
    for i, name in enumerate(customer_names):
        first, last = name.split(" ")
        email = f"{first.lower()}.{last.lower()}@example.com"
        country = countries[i % len(countries)]
        signup_date = (base_date + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
        customers_data.append((name, email, country, signup_date))
        
    cursor.executemany(
        "INSERT INTO customers (name, email, country, signup_date) VALUES (?, ?, ?, ?)",
        customers_data
    )

    # 2. Populate Products
    products_list = [
        # Electronics
        ("Premium Laptop", "Electronics", 1299.99, 45),
        ("Wireless Headphones", "Electronics", 149.99, 120),
        ("Smart Watch", "Electronics", 249.99, 75),
        ("Mechanical Keyboard", "Electronics", 89.99, 150),
        ("Computer Monitor 27''", "Electronics", 329.99, 60),
        # Office Supplies
        ("Ergonomic Chair", "Office Supplies", 199.99, 30),
        ("Standing Desk", "Office Supplies", 449.99, 15),
        ("Notebook Pack of 5", "Office Supplies", 12.49, 500),
        ("Gel Pens Pack of 10", "Office Supplies", 7.99, 800),
        ("Desk Organizer", "Office Supplies", 24.99, 200),
        # Furniture
        ("Bookshelf 5-Tier", "Furniture", 119.99, 40),
        ("Coffee Table", "Furniture", 159.99, 25),
        ("Leather Sofa", "Furniture", 899.99, 10),
        ("Floor Lamp", "Furniture", 49.99, 90),
        ("Dining Table Set", "Furniture", 699.99, 8)
    ]
    cursor.executemany(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        products_list
    )

    # 3. Populate Orders and Order Items
    # Generate orders over the past 12 months
    order_id_counter = 1
    statuses = ["Completed", "Completed", "Completed", "Completed", "Processing", "Shipped", "Cancelled"]
    
    for month_offset in range(12):
        order_month = base_date + timedelta(days=month_offset * 30)
        # 10-15 orders per month
        num_orders = random.randint(12, 18)
        
        for _ in range(num_orders):
            customer_id = random.randint(1, len(customer_names))
            order_date = (order_month + timedelta(days=random.randint(0, 28))).strftime("%Y-%m-%d")
            status = random.choice(statuses)
            
            # Select random items
            num_items = random.randint(1, 4)
            items_to_add = []
            order_total = 0.0
            
            # Pick distinct products
            chosen_prod_ids = random.sample(range(1, len(products_list) + 1), num_items)
            for prod_id in chosen_prod_ids:
                quantity = random.randint(1, 3)
                # Fetch price
                cursor.execute("SELECT price FROM products WHERE product_id = ?", (prod_id,))
                prod_price = cursor.fetchone()[0]
                item_total = prod_price * quantity
                order_total += item_total
                items_to_add.append((prod_id, quantity, prod_price))
            
            # Insert Order
            cursor.execute(
                "INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES (?, ?, ?, ?)",
                (customer_id, order_date, round(order_total, 2), status)
            )
            
            # Insert Order Items
            for item in items_to_add:
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                    (order_id_counter, item[0], item[1], item[2])
                )
            
            order_id_counter += 1

    # 4. Populate Sales Targets
    # Targets for Electronics, Office Supplies, and Furniture for 2025 (months 1 to 12)
    categories = ["Electronics", "Office Supplies", "Furniture"]
    targets_data = []
    for month in range(1, 13):
        for category in categories:
            if category == "Electronics":
                target = random.randint(3000, 6000)
            elif category == "Furniture":
                target = random.randint(2000, 4500)
            else:
                target = random.randint(500, 1500)
            targets_data.append((2025, month, target, category))
            
    cursor.executemany(
        "INSERT INTO sales_targets (year, month, target_amount, category) VALUES (?, ?, ?, ?)",
        targets_data
    )

    conn.commit()
    conn.close()

def get_db_schema(db_path: str) -> str:
    """
    Inspects the database schema and returns a structured string description
    of tables, columns, types, primary keys, and foreign keys.
    """
    if not os.path.exists(db_path):
        return "Database does not exist."

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    
    schema_desc = []
    
    for table in tables:
        schema_desc.append(f"Table: {table}")
        
        # Get column definitions
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        # Columns format: (cid, name, type, notnull, dflt_value, pk)
        
        col_strings = []
        pks = []
        for col in columns:
            col_name, col_type, pk = col[1], col[2], col[5]
            col_def = f"  - {col_name} ({col_type})"
            if pk:
                pks.append(col_name)
            col_strings.append(col_def)
            
        if pks:
            schema_desc.append(f"  Primary Key: {', '.join(pks)}")
            
        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table});")
        fks = cursor.fetchall()
        # FK format: (id, seq, table, from, to, on_update, on_delete, match)
        for fk in fks:
            from_col, to_table, to_col = fk[3], fk[2], fk[4]
            schema_desc.append(f"  Foreign Key: {from_col} References {to_table}({to_col})")
            
        schema_desc.extend(col_strings)
        schema_desc.append("")  # Empty line separator

    conn.close()
    return "\n".join(schema_desc)

def is_query_safe(sql_query: str) -> bool:
    """
    Analyzes a SQL query to verify it is safe (read-only SELECT query).
    Blocks statements that alter or modify the database state.
    """
    # Clean whitespace and convert to lowercase
    query_clean = re.sub(r'\s+', ' ', sql_query).strip().lower()
    
    # Remove strings inside quotes to avoid false positives inside text literals
    # e.g., SELECT * FROM customers WHERE name = 'Delete Me'
    query_clean = re.sub(r"'(?:''|[^'])*'", '', query_clean)
    query_clean = re.sub(r'"(?:""|[^"])*"', '', query_clean)
    
    # Check for modification commands (words must be surrounded by word boundaries to avoid matching things like 'update_date')
    forbidden_patterns = [
        r'\binsert\b', r'\bupdate\b', r'\bdelete\b', r'\bdrop\b', 
        r'\balter\b', r'\bcreate\b', r'\breplace\b', r'\btruncate\b', 
        r'\bgrant\b', r'\brevoke\b', r'\bexecute\b', r'\bmerge\b'
    ]
    
    for pattern in forbidden_patterns:
        if re.search(pattern, query_clean):
            return False
            
    # Also, verify it starts with SELECT or WITH
    if not (query_clean.startswith("select") or query_clean.startswith("with")):
        return False
        
    return True

def execute_safe_query(db_path: str, sql_query: str) -> dict:
    """
    Executes a SQL query against the database if it passes safety checks.
    Returns results as a dictionary or an error message.
    """
    if not os.path.exists(db_path):
        return {"error": "Database file not found."}
        
    # Standardize query format (remove backticks or markdown fences if generated by LLM)
    sql_clean = sql_query.strip()
    if sql_clean.startswith("```sql"):
        sql_clean = sql_clean[6:]
    if sql_clean.startswith("```"):
        sql_clean = sql_clean[3:]
    if sql_clean.endswith("```"):
        sql_clean = sql_clean[:-3]
    sql_clean = sql_clean.strip()
    
    # Check safety
    if not is_query_safe(sql_clean):
        return {
            "error": "Query blocked. Only read-only SELECT statements are allowed for security reasons."
        }
        
    try:
        conn = sqlite3.connect(db_path)
        # Enable loading of extension or math functions if needed, but standard sqlite is fine.
        df = pd.read_sql_query(sql_clean, conn)
        conn.close()
        
        # Convert df to JSON/dict structure
        columns = list(df.columns)
        records = df.to_dict(orient="records")
        
        return {
            "success": True,
            "query": sql_clean,
            "columns": columns,
            "data": records,
            "row_count": len(df)
        }
    except Exception as e:
        return {
            "success": False,
            "query": sql_clean,
            "error": str(e)
        }
