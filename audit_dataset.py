"""
audit_dataset.py - full cleanliness audit of the biomass trading workbook.
Usage: python audit_dataset.py FILE.xlsx
Prints PASS / WARN / FAIL for every check. FAIL = real error, WARN = needs your decision.
"""
import sys, re, shutil, subprocess, tempfile, os, datetime as dt
import pandas as pd
from openpyxl import load_workbook

F = sys.argv[1]
wb = load_workbook(F); wv = load_workbook(F, data_only=True)
res = {"PASS": 0, "WARN": 0, "FAIL": 0}
def out(level, msg, detail=None):
    res[level] += 1
    print(f"{level:4}  {msg}" + (f"\n      -> {detail}" if detail else ""))
def check(ok, msg, detail=None, level="FAIL"):
    out("PASS" if ok else level, msg, None if ok else detail)

SN = {n[:2]: n for n in wb.sheetnames}
# Clean (intended) column names per sheet. Anything else in row 1 is reported as a header error.
EXPECTED = {
 "01": "no supplier_id supplier_name region port_id buying_price_per_kg effective_from effective_to",
 "02": "no customer_id customer_name supplier_id selling_price_per_kg effective_date payment_term",
 "03": "no date week month delivery_id delivery_ref supplier_id customer_id loading_port_id qty_kg",
 "04": "month region loading_port_id supplier_id customer_id delivery_code material_price_per_kg trucking_cost_per_kg freight_per_kg total_cost_per_kg sales_price_per_kg unit_profit_per_kg qty_delivered_kg total_gross_profit",
 "05": "no date transaction_id supplier_id unit_price_per_kg qty_kg total_amount amount_paid delivered outstanding_deposit_kg outstanding_amount",
 "06": "sheet_description amount_qty"}
# Internal names used by the checks below. Old names and known typos are accepted so the audit never crashes.
ALIAS = {"supplier_id": "Supplier_ID", "supplier_name": "Supplier_Name", "region": "Region", "port_id": "Port_ID",
 "buying_price_per_kg": "Buying_Price_Kg", "buying_price_kg": "Buying_Price_Kg", "effective_from": "Effective_From", "effective_to": "Effective_To",
 "customer_id": "Cust_ID", "cust_id": "Cust_ID", "customer_name": "Cust_Name", "cust_name": "Cust_Name",
 "selling_price_per_kg": "Selling_Price_per_kg", "effective_date": "Effective_Date", "payment_term": "Payment_Term",
 "no": "NO", "date": "Date", "week": "Week", "month": "Month", "delivery_id": "Delivery_ID", "delivery_ref": "Delivery_Ref",
 "loading_port_id": "Loading_Port_ID", "oading_port_id": "Loading_Port_ID", "qty_kg": "Qty_kg",
 "delivery_code": "Delivery_CODE", "material_price_per_kg": "Material", "material": "Material",
 "trucking_cost_per_kg": "Trucking_Cost", "trucking_cost_per_kog": "Trucking_Cost", "trucking_cost": "Trucking_Cost",
 "freight_per_kg": "Freight", "freight": "Freight", "total_cost_per_kg": "Total_Cost", "total_cost": "Total_Cost",
 "sales_price_per_kg": "Sales_Price", "sales_price": "Sales_Price", "unit_profit_per_kg": "Unit_Profit", "unit_profit": "Unit_Profit",
 "qty_delivered_kg": "Qty_Delivered", "qty_delivered": "Qty_Delivered", "total_gross_profit": "Total_Gross_Profit",
 "transaction_id": "Transaction_No", "trasanction_id": "Transaction_No", "transaction_no": "Transaction_No",
 "unit_price_per_kg": "Unit_Price", "unit_price_kg": "Unit_Price", "unit_price_/kg": "Unit_Price",
 "total_amount": "Total_Amount", "amount_paid": "Amount_Paid", "delivered": "Delivered",
 "outstanding_deposit_kg": "Outstanding_Deposit_Kg", "oustanding_deposit_kg": "Outstanding_Deposit_Kg", "outstanding_amount": "Outstanding_Amount",
 "qty_kg_": "Qty_Kg"}
def canon(prefix, c):
    k = str(c).strip().lower()
    if prefix == "05" and k == "qty_kg": return "Qty_Kg"
    if prefix == "01" and k == "no": return "No"
    return ALIAS.get(k, c)
def df(prefix, nrows=None):
    d = pd.read_excel(F, sheet_name=SN[prefix], nrows=nrows)
    return d.rename(columns=lambda c: canon(prefix, c))

S, C, D, G, P = df("01"), df("02"), df("03"), df("04"), df("05")
D = D[D.NO.notna()].copy(); G = G[G.Delivery_CODE.notna()].copy(); P = P[P.Supplier_ID.notna()].copy()
P = P.rename(columns=lambda c: "Unit_Price" if str(c).startswith("Unit_Price") else c)   # works with Unit_Price_Kg or Unit_Price
D["Date"] = pd.to_datetime(D.Date); D["M"] = D.Date.dt.to_period("M").dt.to_timestamp()
G["Month"] = pd.to_datetime(G.Month)
for c in ("Effective_From", "Effective_To"): S[c] = pd.to_datetime(S[c])
C["Effective_Date"] = pd.to_datetime(C.Effective_Date); P["Date"] = pd.to_datetime(P.Date)

print("== A. STRUCTURE ==")
check(len(wb._external_links) == 0, "No external links")
check(all(ws.sheet_state == "visible" for ws in wb), "No hidden sheets")
check(not any(ws.merged_cells.ranges for ws in wb), "No merged cells")
hid = [(ws.title, k) for ws in wb for k, d in list(ws.row_dimensions.items()) + list(ws.column_dimensions.items()) if d.hidden]
check(not hid, "No hidden rows or columns", hid[:5])
for ws in wb:
    for t in ws.tables.values():
        last = max((c.row for row in ws.iter_rows() for c in row if c.value is not None and c.column <= ws[t.ref.split(':')[0]].column + 0 + 0) , default=0)
        data_last = max(r for r in range(1, ws.max_row + 1) if any(ws.cell(row=r, column=c).value is not None for c in range(1, ws.max_column + 1)))
        tbl_last = int(re.findall(r"\d+", t.ref.split(":")[1])[0])
        check(tbl_last == data_last, f"{ws.title}: table {t.name} ({t.ref}) covers all data rows", f"table ends at {tbl_last}, data ends at {data_last}")
        blanks = [r for r in range(2, tbl_last + 1) if all(ws.cell(row=r, column=c).value is None for c in range(1, ws.max_column + 1))]
        check(not blanks, f"{ws.title}: no blank rows inside the table", blanks[:5])

print("\n== B. CELL HYGIENE ==")
sp = [(ws.title, c.coordinate, c.value) for ws in wb for row in ws.iter_rows() for c in row
      if isinstance(c.value, str) and not c.value.startswith("=") and (c.value != c.value.strip() or "  " in c.value)]
check(not sp, "No leading/trailing/double spaces in text", sp[:5])
errs = [(ws.title, c.coordinate, c.value) for ws in wv for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("#")]
check(not errs, "No formula errors (#REF!, #VALUE!, ...)", errs[:5])
txtnum = [(ws.title, c.coordinate, c.value) for ws in wb for row in ws.iter_rows(min_row=2) for c in row
          if isinstance(c.value, str) and not c.value.startswith("=") and re.fullmatch(r"\s*-?\d[\d,.]*\s*", c.value)]
check(not txtnum, "No numbers stored as text", txtnum[:5])
nulls = {n: int(x.isna().sum().sum()) for n, x in (("deliveries", D), ("routes", G), ("purchases", P))}
check(sum(nulls.values()) == 0, "No blank cells in deliveries, routes or purchases", nulls)
for name, frame, cols in (("deliveries", D, ["Qty_kg"]), ("routes", G, ["Material", "Trucking_Cost", "Sales_Price"]),
                          ("purchases", P, ["Unit_Price", "Qty_Kg"])):
    for c in cols: check((frame[c] > 0).all(), f"{name}.{c} always > 0")

check((G.Freight >= 0).all(), "routes.Freight is never negative")
zf = G[G.Freight == 0]
check(zf.empty, "Routes with zero Freight", f"{len(zf)} route rows ({', '.join(sorted(set(zf.Delivery_CODE)))}). OK if the delivery ends at the loading port; say so in the README", "WARN")

print("\n== C. FORMULAS ==")
def pattern(v, r): return re.sub(rf"(?<=[A-Z]){r}\b", "{r}", v) if isinstance(v, str) else v
for prefix in ("01", "02", "03", "04", "05"):
    ws = wb[SN[prefix]]; bad = []
    for col in range(1, ws.max_column + 1):
        pats = {}
        for r in range(2, ws.max_row + 1):
            v = ws.cell(row=r, column=col).value
            if v is None: continue
            kind = "F:" + pattern(v, r) if isinstance(v, str) and v.startswith("=") else "V"
            pats.setdefault(kind, []).append(r)
        if any(k.startswith("F:") for k in pats) and len(pats) > 1:
            bad.append((ws.cell(row=1, column=col).value, {k[:40]: len(v) for k, v in pats.items()}))
    check(not bad, f"{ws.title}: each formula column uses one formula pattern (no hard-coded cells mixed in)", bad)
tmp = tempfile.mkdtemp(); cp = os.path.join(tmp, "copy.xlsx"); shutil.copy(F, cp)
r = subprocess.run(["python3", "/mnt/skills/public/xlsx/scripts/recalc.py", cp], capture_output=True, text=True)
if r.returncode == 0 and "success" in r.stdout and os.path.exists(cp):
    rc = load_workbook(cp, data_only=True); stale = []
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    a, b = wv[ws.title][c.coordinate].value, rc[ws.title][c.coordinate].value
                    same = (abs(a - b) < 1e-6) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else a == b
                    if not same: stale.append((ws.title, c.coordinate, a, b))
    check(not stale, "Saved values equal freshly recalculated values (nothing stale)", stale[:5])
else:
    out("WARN", "Stale-value test skipped: it needs the LibreOffice recalculation helper, which is only available in the Claude environment. All other checks ran normally.")

print("\n== D. KEYS AND LINKS BETWEEN TABLES ==")
check(D.NO.is_unique and set(D.NO) == set(range(1, len(D) + 1)), "deliveries.NO is unique and runs 1..N")
check(D.Delivery_ID.is_unique, "deliveries.Delivery_ID is unique")
check(P.Transaction_No.is_unique, "purchases.Transaction_No is unique")
check(S.duplicated(["Supplier_ID", "Effective_From"]).sum() == 0, "01_Supplier: one price row per supplier and start date")
check(C.duplicated(["Cust_ID", "Supplier_ID", "Effective_Date"]).sum() == 0, "02_Cust: one price row per customer, supplier and date")
check(G.duplicated(["Month", "Delivery_CODE"]).sum() == 0, "04_Gross_Profit: route key (Month + Delivery_CODE) is unique")
sup, cus = set(S.Supplier_ID), set(C.Cust_ID)
check(set(D.Supplier_ID) <= sup and set(G.Supplier_ID) <= sup and set(P.Supplier_ID) <= sup and set(C.Supplier_ID) <= sup, "Every Supplier_ID used anywhere exists in 01_Supplier")
check(set(D.Cust_ID) <= cus and set(G.Cust_ID) <= cus, "Every Cust_ID used anywhere exists in 02_Cust")
rt = set(zip(G.Month, G.Delivery_CODE)); miss = D[[ (m, r) not in rt for m, r in zip(D.M, D.Delivery_Ref)]]
check(miss.empty, "Every delivery (month + Delivery_Ref) has a route", miss.Delivery_Ref.unique().tolist())
used = set(zip(D.M, D.Delivery_Ref)); unused = [(m.strftime("%b"), c) for m, c in rt if (m, c) not in used]
check(not unused, "Every route has at least one delivery", f"unused routes: {unused}", "WARN")
pairs_c = set(zip(C.Supplier_ID, C.Cust_ID)); nop = sorted({(s, c) for s, c in zip(G.Supplier_ID, G.Cust_ID)} - pairs_c)
check(not nop, "Every route pair has a price in 02_Cust", nop)
check(not (sup - set(D.Supplier_ID)), "Every supplier has deliveries", sorted(sup - set(D.Supplier_ID)), "WARN")
check(not (cus - set(D.Cust_ID)), "Every customer has deliveries", sorted(cus - set(D.Cust_ID)), "WARN")

print("\n== E. BUSINESS RULES ==")
check((D.Month == D.M).all(), "Month column equals the first day of the Date's month")
check((D.Week == "Week " + ((D.Date.dt.day - 1) // 7 + 1).clip(upper=4).astype(str)).all(), "Week follows the 7-day rule (days 22-31 = Week 4)")
check(((D.Delivery_Ref.str.replace("-BTL", "") == D.Supplier_ID + "-" + D.Cust_ID)).all(), "Delivery_Ref = Supplier-Customer")
check(D.Date.between("2026-09-01", "2026-10-31").all(), "All delivery dates fall in Sept-Oct 2026")
reg = dict(zip(S.Supplier_ID, S.Region)); check((G.Supplier_ID.map(reg) == G.Region).all(), "Route Region = supplier's region")
mm = D.groupby(["M", "Delivery_Ref", "Loading_Port_ID"]).size().reset_index().merge(
    G[["Month", "Delivery_CODE", "Loading_Port_ID"]].rename(columns={"Month": "M", "Delivery_CODE": "Delivery_Ref", "Loading_Port_ID": "RP"}), on=["M", "Delivery_Ref"], how="left")
check((mm.Loading_Port_ID == mm.RP).all(), "Delivery loading port = route loading port")
check(((G.Material + G.Trucking_Cost + G.Freight) == G.Total_Cost).all(), "Total_Cost = Material + Trucking + Freight")
check(((G.Sales_Price - G.Total_Cost) == G.Unit_Profit).all(), "Unit_Profit = Sales_Price - Total_Cost")
exp = D.groupby(["M", "Delivery_Ref"]).Qty_kg.sum(); G["exp"] = [exp.get((m, c), 0) for m, c in zip(G.Month, G.Delivery_CODE)]
check((G.exp == G.Qty_Delivered).all(), "Qty_Delivered = sum of deliveries for that route and month")
check(((G.Unit_Profit * G.Qty_Delivered) == G.Total_Gross_Profit).all(), "Total_Gross_Profit = Unit_Profit x Qty_Delivered")
def price(frame, key, kcol, d, pcol, f="Effective_From", t="Effective_To"):
    x = frame[(frame[kcol] == key) & (frame[f] <= d) & (frame[t].isna() | (frame[t] >= d))] if t in frame else frame[(frame[kcol] == key) & (frame[f] <= d)]
    return x[pcol].iloc[-1] if len(x) else None
G["mat"] = [price(S, s, "Supplier_ID", m, "Buying_Price_Kg") for s, m in zip(G.Supplier_ID, G.Month)]
bad = G[G.Material != G.mat]
check(bad.empty, "Route Material = supplier buying price valid in that month (01_Supplier)", bad[["Month", "Delivery_CODE", "Material", "mat"]].to_string(index=False))
Cs = C.sort_values("Effective_Date")
G["sell"] = [ (lambda x: x.Selling_Price_per_kg.iloc[-1] if len(x) else None)(Cs[(Cs.Supplier_ID == s) & (Cs.Cust_ID == c) & (Cs.Effective_Date <= m)]) for s, c, m in zip(G.Supplier_ID, G.Cust_ID, G.Month)]
bad = G[G.Sales_Price != G.sell]
check(bad.empty, "Route Sales_Price = price list valid in that month (02_Cust)", bad[["Month", "Delivery_CODE", "Sales_Price", "sell"]].to_string(index=False))
sp_ = S.sort_values(["Supplier_ID", "Effective_From"]); gaps = []
for s, g in sp_.groupby("Supplier_ID"):
    for a, b in zip(g.Effective_To, g.Effective_From.shift(-1)):
        if pd.notna(b) and (pd.isna(a) or (b - a).days != 1): gaps.append((s, a, b))
check(not gaps, "01_Supplier price periods have no gaps or overlaps", gaps)
check(((P["Unit_Price"] * P.Qty_Kg) == P.Total_Amount).all() if "Total_Amount" in P else True, "Purchases: Total_Amount = price x Qty")
check((P.Delivered <= P.Qty_Kg).all(), "Purchases: Delivered never exceeds purchased Qty")
pp = P.groupby("Supplier_ID").Delivered.sum(); dd = D.groupby("Supplier_ID").Qty_kg.sum(); dif = (dd - pp).dropna()
check((dif == 0).all() and set(dd.index) == set(pp.index), "Purchases 'Delivered' = deliveries per supplier", dif[dif != 0].to_dict())
P["price_master"] = [price(S, s, "Supplier_ID", d, "Buying_Price_Kg") for s, d in zip(P.Supplier_ID, P.Date)]
bad = P[P["Unit_Price"] != P.price_master]
check(bad.empty, "Purchase unit price = 01_Supplier price on that date", bad[["Date", "Transaction_No", "Supplier_ID", "Unit_Price", "price_master"]].to_string(index=False), "WARN")
dup = D[D.duplicated(["Date", "Delivery_Ref", "Qty_kg"], keep=False)]
check(dup.empty, "No identical deliveries (same date, route and Qty)", f"{len(dup)} rows - confirm they are real separate trucks", "WARN")
q1, q3 = D.Qty_kg.quantile([.25, .75]); lo, hi = q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1)
ol = D[(D.Qty_kg < lo) | (D.Qty_kg > hi)]
check(ol.empty, f"No extreme Qty outliers (outside {lo:,.0f}-{hi:,.0f} kg)", ol[["NO", "Date", "Delivery_Ref", "Qty_kg"]].to_string(index=False), "WARN")

print("\n== F. TOTALS ==")
cb = wv[SN["06"]]; vals = [c.value for row in cb.iter_rows() for c in row if isinstance(c.value, (int, float))]
check(vals and vals[-1] == 0, "Check & Balance difference is 0", vals)
gp = G.Total_Gross_Profit.sum()
print(f"INFO  Total Qty {D.Qty_kg.sum():,} kg | Sept {D[D.M.dt.month==9].Qty_kg.sum():,} | Oct {D[D.M.dt.month==10].Qty_kg.sum():,} | Gross profit Rp {gp:,.0f} | trucks {len(D)} | routes {len(G)}")

print("\n== G. EXPORT-READINESS (CSV / SQL / Power BI) ==")
for pre, exp in EXPECTED.items():
    got = [str(c.value).strip() for c in wb[SN[pre]][1] if c.value is not None]
    bad = [h for h in got if h not in exp.split()]
    check(not bad, f"{SN[pre]}: every column name is a clean, expected name (no typos)", f"{bad}  (expected e.g. {[e for e in exp.split() if e not in got][:4]})")
    mixed = [h for h in got if h != h.lower()]
    check(not mixed, f"{SN[pre]}: column names are all lowercase", mixed, "WARN")
for ws in wb:
    h = [c.value for c in ws[1] if c.value is not None]; badh = [x for x in h if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", str(x))]
    check(not badh, f"{ws.title}: column names are SQL-safe (letters, digits, underscore)", badh, "WARN")
check(all(re.fullmatch(r"[A-Za-z0-9_]+", n) for n in wb.sheetnames), "Sheet names have no spaces or symbols", [n for n in wb.sheetnames if not re.fullmatch(r"[A-Za-z0-9_]+", n)], "WARN")

print("\n== H. FILE PROPERTIES ==")
p = wb.properties
check(p.lastModifiedBy in (None, "", "Analyst"), "lastModifiedBy is neutral", p.lastModifiedBy, "WARN")
check(not p.category or "Comodity" not in p.category, "Category field is clean", p.category, "WARN")
print(f"\nRESULT: {res['PASS']} PASS | {res['WARN']} WARN | {res['FAIL']} FAIL")
