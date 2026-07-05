# SQL Query Guidelines — Analytics Q&A Copilot

## Actual Table Schema

```
customers:    customer_id, name, email, country, signup_date
products:     product_id, name, category, price, stock
orders:       order_id, customer_id, order_date, total_amount, status
order_items:  item_id, order_id, product_id, quantity, price
sales_targets: target_id, year, month, target_amount, category
```

## Critical SQLite Rules
1. Use strftime('%Y', order_date) for year filtering — NOT YEAR() or EXTRACT()
2. Use strftime('%m', order_date) for month filtering — NOT MONTH()
3. Use strftime('%Y-%m', order_date) for grouping by month
4. For sales_targets month filter use: WHERE year=2025 AND month=3 (integer, not string)
5. Always alias aggregated columns: SUM(total_amount) AS total_sales
6. Exclude cancelled/returned: WHERE status NOT IN ('cancelled','returned')

## Common Query Patterns

### Top N Customers by Spend
```sql
SELECT c.name, SUM(o.total_amount) AS total_spend
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE o.status NOT IN ('cancelled','returned')
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC
LIMIT 5;
```

### Sales by Category per Month
```sql
SELECT strftime('%Y-%m', o.order_date) AS month,
       p.category,
       SUM(oi.quantity * oi.price) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status NOT IN ('cancelled','returned')
  AND strftime('%Y', o.order_date) = '2025'
GROUP BY month, p.category
ORDER BY month, revenue DESC;
```

### Cancelled Orders Count and Value
```sql
SELECT COUNT(*) AS cancelled_count,
       SUM(total_amount) AS total_value
FROM orders
WHERE status = 'cancelled';
```

### Sales vs Target for a Specific Month
```sql
SELECT st.category,
       st.target_amount,
       COALESCE(SUM(oi.quantity * oi.price), 0) AS actual_sales,
       ROUND(COALESCE(SUM(oi.quantity * oi.price), 0) * 100.0 / st.target_amount, 1) AS attainment_pct
FROM sales_targets st
LEFT JOIN products p ON p.category = st.category
LEFT JOIN order_items oi ON oi.product_id = p.product_id
LEFT JOIN orders o ON o.order_id = oi.order_id
    AND strftime('%Y', o.order_date) = CAST(st.year AS TEXT)
    AND CAST(strftime('%m', o.order_date) AS INTEGER) = st.month
    AND o.status NOT IN ('cancelled','returned')
WHERE st.year = 2025 AND st.month = 3
GROUP BY st.category, st.target_amount;
```

### Low Stock Products
```sql
SELECT name, category, price, stock
FROM products
WHERE stock < 50
ORDER BY stock ASC;
```

### Best Selling Products
```sql
SELECT p.name, p.category,
       SUM(oi.quantity) AS units_sold
FROM products p
JOIN order_items oi ON oi.product_id = p.product_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status NOT IN ('cancelled','returned')
GROUP BY p.product_id, p.name, p.category
ORDER BY units_sold DESC
LIMIT 10;
```
