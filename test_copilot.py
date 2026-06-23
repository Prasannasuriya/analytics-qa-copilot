import os
import unittest
import tempfile
import sqlite3

# Adjust paths to import backend modules
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_database, get_db_schema, is_query_safe, execute_safe_query

class TestAnalyticsCopilot(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        
    def tearDown(self):
        # Close and remove the temporary database file
        os.close(self.db_fd)
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def test_database_initialization_and_schema(self):
        """Test database is created correctly with tables and schema is readable."""
        # Initialize
        init_database(self.db_path)
        
        # Verify file is not empty
        self.assertTrue(os.path.exists(self.db_path))
        self.assertGreater(os.path.getsize(self.db_path), 0)
        
        # Parse schema
        schema = get_db_schema(self.db_path)
        
        # Verify key tables exist in parsed schema text
        self.assertIn("Table: customers", schema)
        self.assertIn("Table: products", schema)
        self.assertIn("Table: orders", schema)
        self.assertIn("Table: order_items", schema)
        self.assertIn("Table: sales_targets", schema)
        
        # Verify columns exist
        self.assertIn("customer_id", schema)
        self.assertIn("total_amount", schema)
        self.assertIn("target_amount", schema)

    def test_sql_safety_check(self):
        """Test that read-only queries are allowed and modifying statements are blocked."""
        # Safe Queries
        self.assertTrue(is_query_safe("SELECT * FROM customers;"))
        self.assertTrue(is_query_safe("SELECT name, email FROM customers WHERE country = 'USA';"))
        self.assertTrue(is_query_safe("WITH monthly_sales AS (SELECT order_date FROM orders) SELECT * FROM monthly_sales;"))
        self.assertTrue(is_query_safe("select count(customer_id) from customers;"))
        
        # Unsafe / Modifying Queries
        self.assertFalse(is_query_safe("DELETE FROM customers;"))
        self.assertFalse(is_query_safe("INSERT INTO customers (name, email) VALUES ('John', 'john@test.com');"))
        self.assertFalse(is_query_safe("UPDATE products SET price = 0.0 WHERE product_id = 1;"))
        self.assertFalse(is_query_safe("DROP TABLE orders;"))
        self.assertFalse(is_query_safe("ALTER TABLE customers ADD COLUMN age INTEGER;"))
        self.assertFalse(is_query_safe("CREATE TABLE hack (id INT);"))
        
        # SQL Injection / Multi-statement check
        self.assertFalse(is_query_safe("SELECT * FROM customers; DROP TABLE orders;"))
        self.assertFalse(is_query_safe("SELECT * FROM customers; DELETE FROM orders WHERE 1=1;"))
        
        # Case insensitive check
        self.assertFalse(is_query_safe("select * from customers; uPdAtE products set price = 100;"))

    def test_execute_query(self):
        """Test query execution behaviors (success, syntax error, safety block)."""
        init_database(self.db_path)
        
        # 1. Success execution
        res = execute_safe_query(self.db_path, "SELECT COUNT(*) as count FROM customers;")
        self.assertTrue(res["success"])
        self.assertEqual(res["row_count"], 1)
        self.assertEqual(res["columns"], ["count"])
        self.assertGreater(res["data"][0]["count"], 0)
        
        # 2. Syntax error execution
        res_error = execute_safe_query(self.db_path, "SELECT * FROM non_existent_table;")
        self.assertFalse(res_error["success"])
        self.assertIn("no such table", res_error["error"])
        
        # 3. Blocked execution
        res_blocked = execute_safe_query(self.db_path, "DELETE FROM orders;")
        self.assertIn("error", res_blocked)
        self.assertIn("Query blocked", res_blocked["error"])

if __name__ == "__main__":
    unittest.main()
