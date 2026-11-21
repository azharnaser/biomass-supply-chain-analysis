-- =====================================================================
-- Biomass supply chain analysis: business questions (Day 2)
-- Uses: window functions (RANK, LAG, running sums), CTEs and joins.
-- How to use: highlight ONE query (from WITH/SELECT to the semicolon),
-- press the play button, and compare with the "Expected" line.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Q1. Concentration: share of kg and of profit from the top 3 suppliers
-- Question: how dependent is the business on a few suppliers?  (top 3 by kg and top 3 by profit)
-- Expected: top3_kg_pct 61.4, top3_profit_pct 59.2
-- ---------------------------------------------------------------------
WITH k AS (SELECT supplier_id, SUM(qty_kg) AS kg FROM deliveries GROUP BY supplier_id),
g AS (SELECT supplier_id, SUM(total_gross_profit) AS gp FROM gross_profit GROUP BY supplier_id),
j AS (SELECT k.supplier_id, k.kg, g.gp,
             RANK() OVER (ORDER BY k.kg DESC) AS rk_kg,
             RANK() OVER (ORDER BY g.gp DESC) AS rk_gp
      FROM k JOIN g ON g.supplier_id = k.supplier_id)
SELECT ROUND(SUM(CASE WHEN rk_kg <= 3 THEN kg END) * 100.0 / SUM(kg), 1) AS top3_kg_pct,
       ROUND(SUM(CASE WHEN rk_gp <= 3 THEN gp END) * 100.0 / SUM(gp), 1) AS top3_profit_pct
FROM j;


-- ---------------------------------------------------------------------
-- Q2. Volume share vs profit share per supplier
-- Question: is the biggest supplier also the most profitable per kg?
-- Expected: 9 rows. STP 34.9% of kg but 25.4% of profit (69.3 per kg); STD 12.5% of kg but 21.6% of profit (164.2 per kg); BGM lowest at 37.6 per kg
-- ---------------------------------------------------------------------
WITH k AS (SELECT supplier_id, SUM(qty_kg) AS kg FROM deliveries GROUP BY supplier_id),
g AS (SELECT supplier_id, SUM(total_gross_profit) AS gp FROM gross_profit GROUP BY supplier_id)
SELECT k.supplier_id, k.kg,
       ROUND(k.kg * 100.0 / SUM(k.kg) OVER (), 1) AS kg_share_pct,
       g.gp,
       ROUND(g.gp * 100.0 / SUM(g.gp) OVER (), 1) AS profit_share_pct,
       ROUND(g.gp * 1.0 / k.kg, 1) AS profit_per_kg
FROM k JOIN g ON g.supplier_id = k.supplier_id
ORDER BY k.kg DESC;


-- ---------------------------------------------------------------------
-- Q3. Pareto: cumulative share of profit by supplier
-- Question: how many suppliers produce most of the profit?
-- Expected: 9 rows. STP 25.4, STD 47.0, BIS 59.2, BSP 69.9 ... BGM 100.0
-- ---------------------------------------------------------------------
WITH g AS (SELECT supplier_id, SUM(total_gross_profit) AS gp FROM gross_profit GROUP BY supplier_id)
SELECT supplier_id, gp,
       ROUND(SUM(gp) OVER (ORDER BY gp DESC) * 100.0 / SUM(gp) OVER (), 1) AS cumulative_pct
FROM g
ORDER BY gp DESC;


-- ---------------------------------------------------------------------
-- Q4. Month-over-month volume per supplier (LAG)
-- Question: which suppliers grew or shrank from September to October?
-- Expected: 15 rows. BGM -38.1, BIS -87.9, BSP -37.7, SAF -38.6, STD -33.9, STP +37.0. KMB and SSP only in Sept, PMK only in Oct (change is empty)
-- ---------------------------------------------------------------------
WITH m AS (SELECT supplier_id, month, SUM(qty_kg) AS kg FROM deliveries GROUP BY supplier_id, month)
SELECT supplier_id, month, kg,
       LAG(kg) OVER (PARTITION BY supplier_id ORDER BY month) AS prev_kg,
       ROUND((kg - LAG(kg) OVER (PARTITION BY supplier_id ORDER BY month)) * 100.0
             / LAG(kg) OVER (PARTITION BY supplier_id ORDER BY month), 1) AS change_pct
FROM m
ORDER BY supplier_id, month;


-- ---------------------------------------------------------------------
-- Q5. Purchased vs delivered vs outstanding per supplier
-- Question: how much of what we bought has not been delivered yet?
-- Expected: 9 rows. BGM 210000 / 166090 / 43910 (36225750), STP 770000 / 745350 / 24650. Totals: 2250000 / 2136200 / 113800
-- ---------------------------------------------------------------------
SELECT supplier_id,
       SUM(qty_kg)                 AS purchased_kg,
       SUM(delivered)              AS delivered_kg,
       SUM(outstanding_deposit_kg) AS outstanding_kg,
       SUM(outstanding_amount)     AS outstanding_amount
FROM purchasing_history
GROUP BY supplier_id
ORDER BY outstanding_kg DESC;


-- ---------------------------------------------------------------------
-- Q6. Best and worst routes by profit per kg
-- Question: which routes earn the most and the least per kg? (top 3 and bottom 3, ties included)
-- Expected: 7 rows. Best: STD-BUMI Oct 200 (88040 kg), STD-JAGO Oct 190, BGM-CAKRA Sept 180. Worst: BGM-BUMI Sept and Oct 30 (94150 and 63520 kg), BSP-JAGO 40
-- ---------------------------------------------------------------------
WITH r AS (
    SELECT delivery_code, month, unit_profit_per_kg, qty_delivered_kg,
           RANK() OVER (ORDER BY unit_profit_per_kg DESC) AS best_rank,
           RANK() OVER (ORDER BY unit_profit_per_kg ASC)  AS worst_rank
    FROM gross_profit
)
SELECT delivery_code, month, unit_profit_per_kg, qty_delivered_kg
FROM r
WHERE best_rank <= 3 OR worst_rank <= 3
ORDER BY unit_profit_per_kg DESC, delivery_code;


-- ---------------------------------------------------------------------
-- Q7. Trucks and average kg per truck by port
-- Question: do trucks carry different loads at different ports?
-- Expected: BTL 121 trucks / 1186340 kg / 9804 avg, SPT 42 / 396980 / 9452, BJM 60 / 552880 / 9215
-- ---------------------------------------------------------------------
SELECT loading_port_id,
       COUNT(*)              AS trucks,
       SUM(qty_kg)           AS total_kg,
       ROUND(AVG(qty_kg), 0) AS avg_kg_per_truck
FROM deliveries
GROUP BY loading_port_id
ORDER BY avg_kg_per_truck DESC;


-- ---------------------------------------------------------------------
-- Q8. Kg per week within each month
-- Question: how is volume spread across the weeks?
-- Expected: 8 rows. Sept 137470 / 331470 / 397630 / 339560. Oct 350980 / 194800 / 195850 / 188440
-- ---------------------------------------------------------------------
SELECT month, week, SUM(qty_kg) AS total_kg
FROM deliveries
GROUP BY month, week
ORDER BY month, week;


-- ---------------------------------------------------------------------
-- Q9. September vs October: volume, profit and margin
-- Question: how much did volume and profit fall in October?
-- Expected: Sept 1206130 kg / 116180570 profit / 96.3 per kg. Oct 930070 / 87425770 / 94.0. Change: kg -22.9%, profit -24.8%
-- ---------------------------------------------------------------------
WITH m AS (SELECT month, SUM(qty_delivered_kg) AS kg, SUM(total_gross_profit) AS gp FROM gross_profit GROUP BY month)
SELECT month, kg, gp,
       ROUND(gp * 1.0 / kg, 1) AS profit_per_kg,
       ROUND((kg - LAG(kg) OVER (ORDER BY month)) * 100.0 / LAG(kg) OVER (ORDER BY month), 1) AS kg_change_pct,
       ROUND((gp - LAG(gp) OVER (ORDER BY month)) * 100.0 / LAG(gp) OVER (ORDER BY month), 1) AS profit_change_pct
FROM m
ORDER BY month;


-- ---------------------------------------------------------------------
-- Q10. Profit and profit per kg per customer (join deliveries to routes)
-- Question: which customers bring the most profit, and at what margin?
-- Expected: BUMI 74754800 (101.0 per kg), AGRO 52967930 (106.6), JAGO 27085300, VINA 24239070 (74.3), YAKIN 20273860 (73.6), ORCA 2769780, CAKRA 1515600. Sum 203606340
-- ---------------------------------------------------------------------
SELECT d.customer_id,
       SUM(d.qty_kg)                          AS total_kg,
       SUM(d.qty_kg * g.unit_profit_per_kg)   AS gross_profit,
       ROUND(SUM(d.qty_kg * g.unit_profit_per_kg) * 1.0 / SUM(d.qty_kg), 1) AS profit_per_kg
FROM deliveries d
JOIN gross_profit g
  ON d.delivery_ref = g.delivery_code
 AND d.month = g.month
GROUP BY d.customer_id
ORDER BY gross_profit DESC;
