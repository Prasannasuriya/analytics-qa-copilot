# Database Querying Guidelines

- **Sales Target Calculations**:
  To compute sales performance against monthly targets, join orders with sales_targets on category and date. Note that sales_targets defines year, month, 	arget_amount and category. 
  Use:
  strftime('%Y', orders.order_date) = sales_targets.year and CAST(strftime('%m', orders.order_date) AS INTEGER) = sales_targets.month

- **Cancelled Order Rate**:
  The cancellation rate is computed as:
  100.0 * COUNT(CASE WHEN status = 'Cancelled' THEN 1 END) / COUNT(*)
