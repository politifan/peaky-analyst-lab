SELECT c.customer_id,COUNT(o.order_id) AS paid_orders FROM customers c LEFT JOIN orders o ON c.customer_id=o.customer_id AND o.status='paid' AND o.currency='RUB' GROUP BY c.customer_id;
