-- Instamart Copilot -- Part A SQL analysis (SQLite 3.25+).
-- Only completed orders count as revenue or spend. Each query starts with a "-- Qn" marker line.

-- Q1: WHERE then HAVING -- customers whose completed orders above INR 500 total more than INR 8000
SELECT customer_id,
       COUNT(*)                    AS big_orders,
       ROUND(SUM(order_amount), 2) AS total_big_order_amount
FROM orders
WHERE status = 'completed' AND order_amount > 500
GROUP BY customer_id
HAVING SUM(order_amount) > 8000
ORDER BY total_big_order_amount DESC;

-- Q2: three-table join -- revenue by city and product category
SELECT c.city,
       p.category,
       ROUND(SUM(o.order_amount), 2) AS revenue
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN products  p ON p.product_id  = o.product_id
WHERE o.status = 'completed'
GROUP BY c.city, p.category
ORDER BY revenue DESC;

-- Q3: scalar subquery -- products priced above the average catalogue price
SELECT product_id, product_name, category, price_inr
FROM products
WHERE price_inr > (SELECT AVG(price_inr) FROM products)
ORDER BY price_inr DESC;

-- Q4: LEFT JOIN -- customers with no completed order
SELECT c.customer_id, c.city, c.signup_date
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.customer_id AND o.status = 'completed'
WHERE o.order_id IS NULL
ORDER BY c.customer_id;

-- Q5: CTEs -- customers whose total completed spend is above the average customer total
WITH customer_spend AS (
    SELECT customer_id, SUM(order_amount) AS total_spend
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
average_spend AS (
    SELECT AVG(total_spend) AS avg_spend FROM customer_spend
)
SELECT s.customer_id,
       ROUND(s.total_spend, 2) AS total_spend,
       ROUND(a.avg_spend, 2)   AS avg_spend
FROM customer_spend s
CROSS JOIN average_spend a
WHERE s.total_spend > a.avg_spend
ORDER BY s.total_spend DESC;

-- Q6: ranking window functions -- rank customers by completed spend within each city
WITH customer_spend AS (
    SELECT o.customer_id, c.city, ROUND(SUM(o.order_amount), 2) AS total_spend
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.status = 'completed'
    GROUP BY o.customer_id, c.city
)
SELECT city,
       customer_id,
       total_spend,
       RANK()       OVER (PARTITION BY city ORDER BY total_spend DESC) AS rnk,
       DENSE_RANK() OVER (PARTITION BY city ORDER BY total_spend DESC) AS dense_rnk,
       ROW_NUMBER() OVER (PARTITION BY city ORDER BY total_spend DESC, customer_id) AS row_num
FROM customer_spend
ORDER BY city, row_num;

-- Q7: running total -- daily completed revenue and its cumulative sum
WITH daily AS (
    SELECT SUBSTR(order_ts, 1, 10) AS day, SUM(order_amount) AS revenue
    FROM orders
    WHERE status = 'completed'
    GROUP BY day
)
SELECT day,
       ROUND(revenue, 2)                            AS revenue,
       ROUND(SUM(revenue) OVER (ORDER BY day), 2)   AS cumulative_revenue
FROM daily
ORDER BY day;
