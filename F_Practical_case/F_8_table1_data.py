# -*- coding: utf-8 -*-
"""
F_8_table1_data.py  -  numbers behind Table 1, computed from the E_1 results
==========================================================================
For each of the 7 coral-reef cLME sub-segments: the mean annual impact over
2015-2022 (production-based, waterborne + NH3 + NOx summed) and the three
countries whose territorial emissions cause the largest share of it.

Reads   1. results/CBA_vs_PBA/<flow>_<year>_<lme>.csv         (E_1, BATCH 'original')
        ../E_MRIO_GLORIA_Satellites/0. data_GLORIAv60/GLORIA_ReadMe_060.xlsx (region names)
Writes  2. figures/Table1_data.json   (read by make_table1.js)
        2. figures/Table1_data.csv    (same numbers, for checking)

    python F_8_table1_data.py              original batch (territorial, as in the text)
    python F_8_table1_data.py anchored     GLORIA-anchored batch
"""
import os, sys, json, math
import pandas as pd

HERE  = os.path.dirname(os.path.abspath(__file__))
ANCH  = any(a.lower() == "anchored" for a in sys.argv[1:])
RES   = os.path.join(HERE, "1. results_anchored" if ANCH else "1. results", "CBA_vs_PBA")
FIG   = os.path.join(HERE, "2. figures")
README = os.path.join(HERE, "..", "E_MRIO_GLORIA_Satellites", "0. data_GLORIAv60", "GLORIA_ReadMe_060.xlsx")
YEARS = list(range(2015, 2023))
FLOWS = ["Nleach", "NH3", "NOx"]

# site label, cLME-ss, countries around it (text), bordering GLORIA codes (as in F_2)
SITES = [
    ("Kane'ohe Bay (10)",     "10",    "United States (Hawaiʻi)", ["USA"]),
    ("Bocas del Toro (12.1)", "12_1",  "Panama, Costa Rica, Nicaragua, Honduras, Guatemala, Belize, Mexico, Colombia",
                                       ["PAN", "CRI", "NIC", "HND", "GTM", "BLZ", "MEX", "COL"]),
    ("Crocker Reef (12.2)",   "12_2",  "United States, Cuba, Bahamas", ["USA", "CUB", "BHS"]),
    ("Taiping (36.13)",       "36_13", "Viet Nam, Philippines, Malaysia, Brunei", ["VNM", "PHL", "MYS", "BRN"]),
    ("Dongsha (36.18)",       "36_18", "China, Taiwan, Philippines", ["CHN", "TWN", "PHL"]),
    ("Okinawa (49)",          "49",    "Japan, Taiwan", ["JPN", "TWN"]),
    ("Heron Island (40.4)",   "40_4",  "Australia", ["AUS"]),
]
SHORT = {"USA": "United States", "KOR": "South Korea", "PRK": "North Korea", "RUS": "Russia",
         "IRN": "Iran", "LAO": "Laos", "BOL": "Bolivia", "VEN": "Venezuela", "TZA": "Tanzania",
         "SYR": "Syria", "GBR": "United Kingdom"}

reg = pd.read_excel(README, sheet_name="Regions")
NAME = dict(zip(reg["Region_acronyms"], reg["Region_names"]))
NAME.update(SHORT)

def sig3(v):
    """3 significant figures with thousands separators: 48.5, 8.50, 40,700, 516,000."""
    if v <= 0:
        return "0"
    e = math.floor(math.log10(v))
    r = round(v, -e + 2)
    return f"{r:,.0f}" if e >= 2 else f"{r:.{2 - e}f}"

rows, data, joint = [], [], []
for label, lme, around, border in SITES:
    parts, yrs = [], set()
    for fl in FLOWS:
        for y in YEARS:
            f = os.path.join(RES, f"{fl}_{y}_{lme}.csv")
            if os.path.exists(f):
                d = pd.read_csv(f, usecols=["region", "PBA_kgO2"])
                d["year"] = y
                parts.append(d)
                yrs.add(y)
    if not parts:
        raise SystemExit(f"no CBA_vs_PBA files for {lme} in {RES} - run E_1 first")
    if sorted(yrs) != YEARS:
        raise SystemExit(f"{lme}: years found {sorted(yrs)} - E_1 must cover 2015-2022")
    D = pd.concat(parts, ignore_index=True)
    mean_t = D.groupby("region")["PBA_kgO2"].sum() / len(YEARS) / 1000.0   # t O2-eq per year
    total = mean_t.sum()
    top = mean_t.sort_values(ascending=False).head(3)
    tops = []
    for code, v in top.items():
        name = NAME.get(code, code)
        mark = "*" if str(code).startswith("X") else ("" if code in border else "†")
        tops.append([name + mark, sig3(v), f"{100 * v / total:.1f}"])
        rows.append({"site": label, "lme": lme, "site_total_t": total, "region": code,
                     "country": name, "bordering": code in border, "impact_t": v,
                     "share_pct": 100 * v / total})
    joint.append(100 * top.sum() / total)
    data.append([label, sig3(total), around, tops])
    print(f"{label:24s} total {sig3(total):>9s} t | " +
          " | ".join(f"{c} {v} ({p}%)" for c, v, p in tops))

os.makedirs(FIG, exist_ok=True)
out = {"batch": "anchored" if ANCH else "original", "years": [YEARS[0], YEARS[-1]],
       "joint_top3_pct": [math.floor(min(joint)), math.ceil(max(joint))], "data": data}
with open(os.path.join(FIG, "Table1_data.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
pd.DataFrame(rows).to_csv(os.path.join(FIG, "Table1_data.csv"), index=False)
print(f"top-3 producers jointly: {out['joint_top3_pct'][0]}-{out['joint_top3_pct'][1]}% of each site")
print("written -> 2. figures/Table1_data.json + Table1_data.csv  (then: node make_table1.js)")
