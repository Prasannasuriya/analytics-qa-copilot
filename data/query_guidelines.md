# SQL Query Guidelines for Analytics Q&A Copilot

## General Rules
1. Always write SQLite-compatible SQL — no EXTRACT(), TO_DATE(), or DATEADD().
2. Use `strftime('%Y-%m', date_col)` for monthly filters; `strftime('%Y', date_col)` for annual.
3. Alias every aggregated column, e.g. `SUM(o.total_amount) AS total_sales`.
4. Filter cancelled and returned orders out of revenue calculations unless asked about them explicitly.

## Joining Tables
- `orders` → `customers` via `orders.customer_id = customers.id`
- `order_items` → `orders` via `order_items.order_id = orders.id`
- `order_items` → `products` via `order_items.product_id = products.id`
- `products` → `categories` via `products.category_id = categories.id`
- `sales_targets` → `categories` via `sales_targets.category_id = categories.id`

## Common Query Patterns

### Top-N customers by spend
```sql
SELECT c.name, SUM(o.total_amount) AS total_spend
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.status NOT IN ('cancelled', 'returned')
GROUP BY c.id, c.name
ORDER BY total_spend DESC
LIMIT 5;
```

### Monthly sales by category
```sql
SELECT strftime('%Y-%m', o.order_date) AS month,
       cat.name AS category,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN products p     ON p.id = oi.product_id
JOIN categories cat ON cat.id = p.category_id
WHERE o.status NOT IN ('cancelled', 'returned')
GROUP BY month, cat.id
ORDER BY month, revenue DESC;
```

### Actual vs Target comparison
```sql
SELECT cat.name AS category,
       COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS actual_sales,
       st.target_amount,
       ROUND(COALESCE(SUM(oi.quantity * oi.unit_price), 0) * 100.0 / st.target_amount, 1) AS attainment_pct
FROM sales_targets st
JOIN categories cat ON cat.id = st.category_id
LEFT JOIN products p ON p.category_id = cat.id
LEFT JOIN order_items oi ON oi.product_id = p.id
LEFT JOIN orders o ON o.id = oi.order_id
    AND strftime('%Y-%m', o.order_date) = strftime('%Y-%m', st.target_date)
    AND o.status NOT IN ('cancelled', 'returned')
WHERE strftime('%Y-%m', st.target_date) = '2025-03'
GROUP BY cat.id, cat.name, st.target_amount;
```
