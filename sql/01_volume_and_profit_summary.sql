-- =====================================================================
-- Biomass supply chain analysis: volume and profit summary
-- Database tables: supplier, customer, deliveries, gross_profit,
--                  purchasing_history
-- How to use: select ONE query (highlight it) and press the play button.
-- Compare the result with the "Expected" line above each query.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. Check that the data is loaded
-- ---------------------------------------------------------------------

-- 0a. Row counts. Expected: 10, 24, 223, 31, 20
SELECT 'supplier' AS tbl, COUNT(*) AS n FROM supplier
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'deliveries', COUNT(*) FROM deliveries
UNION ALL SELECT 'gross_profit', COUNT(*) FROM gross_profit
UNION ALL SELECT 'purchasing_history', COUNT(*) FROM purchasing_history;

-- 0b. Total kg delivered. Expected: 2136200
SELECT SUM(qty_kg) AS total_kg
FROM deliveries;


-- ---------------------------------------------------------------------
-- Task 1: trucks and total kg per supplier
-- Expected: STP 76 trucks / 745350 kg, BSP 29 / 298880, STD 30 / 267440
-- ---------------------------------------------------------------------
SELECT supplier_id,
       COUNT(*)    AS trucks,
       SUM(qty_kg) AS total_kg
FROM deliveries
GROUP BY supplier_id
ORDER BY total_kg DESC;


-- ---------------------------------------------------------------------
-- Task 2: share of total volume per customer (%)
-- Expected: BUMI 34.6, AGRO 23.3, VINA 15.3, YAKIN 12.9
-- ---------------------------------------------------------------------
SELECT customer_id,
       SUM(qty_kg) AS total_kg,
       ROUND(SUM(qty_kg) * 100.0 / (SELECT SUM(qty_kg) FROM deliveries), 1) AS share_pct
FROM deliveries
GROUP BY customer_id
ORDER BY total_kg DESC;


-- ---------------------------------------------------------------------
-- Task 3: total kg per loading port
-- Expected: BTL 1186340, BJM 552880, SPT 396980
-- ---------------------------------------------------------------------
SELECT loading_port_id,
       SUM(qty_kg) AS total_kg
FROM deliveries
GROUP BY loading_port_id
ORDER BY total_kg DESC;


-- ---------------------------------------------------------------------
-- Task 4: total kg per month
-- Expected: 2026-09-01 = 1206130, 2026-10-01 = 930070
-- ---------------------------------------------------------------------
SELECT month,
       SUM(qty_kg) AS total_kg
FROM deliveries
GROUP BY month
ORDER BY month;


-- ---------------------------------------------------------------------
-- Task 5: gross profit and profit per kg per supplier
-- Expected: STP 51680750 (69.3 per kg), STD 43914800 (164.2), BIS 24889590 (154.3)
-- ---------------------------------------------------------------------
SELECT supplier_id,
       SUM(qty_delivered_kg)   AS kg,
       SUM(total_gross_profit) AS gross_profit,
       ROUND(SUM(total_gross_profit) * 1.0 / SUM(qty_delivered_kg), 1) AS profit_per_kg
FROM gross_profit
GROUP BY supplier_id
ORDER BY gross_profit DESC;


-- ---------------------------------------------------------------------
-- Task 6: join deliveries to routes and recalculate gross profit
-- Expected: gross_profit 203606340 and rows_joined 223
-- ---------------------------------------------------------------------
SELECT SUM(d.qty_kg * g.unit_profit_per_kg) AS gross_profit,
       COUNT(*)                             AS rows_joined
FROM deliveries d
JOIN gross_profit g
  ON d.delivery_ref = g.delivery_code
 AND d.month = g.month;


-- ---------------------------------------------------------------------
-- Task 7: rank suppliers by gross profit within each month
-- Expected: 15 rows. September rank 1 = STD (22816500), 2 = BIS, 3 = STP
-- ---------------------------------------------------------------------
WITH s AS (
    SELECT month, supplier_id, SUM(total_gross_profit) AS gp
    FROM gross_profit
    GROUP BY month, supplier_id
)
SELECT month,
       supplier_id,
       gp,
       RANK() OVER (PARTITION BY month ORDER BY gp DESC) AS rnk
FROM s
ORDER BY month, rnk;


-- ---------------------------------------------------------------------
-- Task 8: daily kg with running total and 7-delivery-day moving average
-- Expected: 45 rows. First day 36250, running total after day 2 = 62970,
--           final running total = 2136200
-- ---------------------------------------------------------------------
WITH daily AS (
    SELECT date, SUM(qty_kg) AS daily_kg
    FROM deliveries
    GROUP BY date
)
SELECT date,
       daily_kg,
       SUM(daily_kg) OVER (ORDER BY date) AS running_total,
       ROUND(AVG(daily_kg) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) AS moving_avg_7
FROM daily
ORDER BY date;


-- ---------------------------------------------------------------------
-- Task 9: the join trap (a join can silently multiply rows)
-- ---------------------------------------------------------------------

-- 9a. WRONG on purpose: joining on supplier_id only.
--     STD has two price rows, so its deliveries are counted twice.
--     Result: 2403640 kg and 253 rows (should be 2136200 and 223)
SELECT SUM(d.qty_kg) AS total_kg,
       COUNT(*)      AS rows_returned
FROM deliveries d
JOIN supplier s
  ON s.supplier_id = d.supplier_id;

-- 9b. FIXED: each delivery matches only the price period valid on its date.
--     Result: 2136200 kg and 223 rows
SELECT SUM(d.qty_kg) AS total_kg,
       COUNT(*)      AS rows_returned
FROM deliveries d
JOIN supplier s
  ON s.supplier_id = d.supplier_id
 AND d.date >= s.effective_from
 AND d.date <= COALESCE(NULLIF(s.effective_to, ''), '9999-12-31');
