# 3_PBA_before_after_table.py - 7 reef areas x 120 GLORIA sectors, PBA old vs new
# ---------------------------------------------------------------------------
# PBA is the satellite row, so the table needs no MRIO run: for each site this
# reads the row from the ORIGINAL batch ("1.") and the ANCHORED batch ("1b."),
# aggregates the 39,360 columns to the 120 sectors, and writes one workbook:
#   Sheet "Period mean"   site x sector: old, new, diff, diff % (mean 2015-2022)
#   Sheet "By year"       long format (site, sector, year, old, new, diff)
#   Sheet "Site summary"  per site: totals, intl-shipping and household-road
#                         removals, and their share of the old PBA
#   Sheet "Check"         any sector OUTSIDE the two labels' GLORIA keys
#                         (Water transport; Road+Rail+Postal, since GLORIA
#                         splits road emissions across those three industries)
#                         whose change exceeds 1e-9 of the site total - MUST BE EMPTY
# Substances: NOx + NH3 summed (Nleach is untouched by the anchoring and is
# excluded here so the diff columns are pure).
#
# RUN inside E_MRIO_GLORIA_Satellites (after 2_make_anchored_satellites.py):
#   python 3_PBA_before_after_table.py
# OUTPUT: PBA_before_after_7sites.xlsx (falls back to CSVs if openpyxl missing)
# ---------------------------------------------------------------------------
import os
import numpy as np
import pandas as pd
import scipy.sparse as sp

HERE = os.path.dirname(os.path.abspath(__file__))
OLD  = os.path.join(HERE, "1. GLORIAv60_Eutrophication_Satellites")
NEW  = os.path.join(HERE, "1b. GLORIAv60_Eutrophication_Satellites_anchored")
OUT  = os.path.join(HERE, "PBA_before_after_7sites")
YEARS = list(range(2015, 2023))
SITES = [("10", "Kane'ohe Bay"), ("12_1", "Bocas del Toro"), ("12_2", "Crocker Reef"),
         ("36_13", "Taiping"), ("36_18", "Dongsha"), ("49", "Okinawa"),
         ("40_4", "Heron Island")]
CHANGED = {"Water transport",                     # the 1A3d key
           "Road transport", "Rail transport",    # the 1A3b key: GLORIA books
           "Postal and courier services"}         # road emissions across these three

rows = pd.read_csv(os.path.join(OLD, "satellite_row_labels.csv"))
RC = "LME_nb_f_1" if "LME_nb_f_1" in rows.columns else rows.columns[-1]
ridx = {}
for s, _ in SITES:
    hit = rows.index[rows[RC].astype(str).isin([s, s + "_0"])]
    if len(hit):
        ridx[s] = int(hit[0])
lab = pd.read_csv(os.path.join(OLD, "satellite_column_labels.csv"))
lab["sector"] = [l.split(f"({r}) ", 1)[-1].removesuffix(" industry").removesuffix(" product")
                 for l, r in zip(lab["label"], lab["region"])]
sec = lab["sector"].values

rec = []
for batch, base in [("old", OLD), ("new", NEW)]:
    for SUB in ["NOx", "NH3"]:
        for Y in YEARS:
            f = os.path.join(base, f"satellite_{SUB}_{Y}.npz")
            if not os.path.exists(f):
                print(f"{batch} {SUB} {Y}: missing - skipped"); continue
            S = sp.load_npz(f).tocsr()
            for s, ri in ridx.items():
                q = np.asarray(S[ri].todense()).ravel()
                d = pd.DataFrame({"sector": sec, "kgO2": q}).groupby("sector")["kgO2"].sum()
                d = d[d > 0]
                rec.append(pd.DataFrame({"batch": batch, "sub": SUB, "year": Y,
                                         "site": s, "sector": d.index, "kgO2": d.values}))
    print(f"{batch}: read")
R = pd.concat(rec, ignore_index=True)

# combined NOx+NH3, old vs new
g = (R.groupby(["batch", "year", "site", "sector"], as_index=False)["kgO2"].sum()
      .pivot_table(index=["year", "site", "sector"], columns="batch",
                   values="kgO2", fill_value=0.0).reset_index())
g["diff"] = g["old"] - g["new"]
NAME = dict(SITES)
g["site_name"] = g["site"].map(NAME)

pm = g.groupby(["site", "site_name", "sector"], as_index=False)[["old", "new", "diff"]].mean()
pm["diff_pct_of_site"] = 100 * pm["diff"] / pm.groupby("site")["old"].transform("sum")

tot = pm.groupby(["site", "site_name"], as_index=False)[["old", "new", "diff"]].sum()
wt = pm[pm.sector == "Water transport"].set_index("site")["diff"]
rd = (pm[pm.sector.isin(["Road transport", "Rail transport",
                         "Postal and courier services"])]      # the full 1A3b key
      .groupby("site")["diff"].sum())
summ = tot.set_index("site")
summ["intl_shipping"] = wt
summ["household_road"] = rd
summ["intl_ship_pct_of_PBA"] = 100 * wt / summ["old"]
summ["household_road_pct_of_PBA"] = 100 * rd / summ["old"]
summ = summ.reindex([s for s, _ in SITES]).reset_index()

chk = pm[(~pm.sector.isin(CHANGED))
         & (pm["diff"].abs() > 1e-9 * pm.groupby("site")["old"].transform("sum"))]
print("\nCHECK - sectors outside the labels' GLORIA keys with a change:",
      "NONE (as required)" if chk.empty else f"{len(chk)} rows - INVESTIGATE")
print("\nSite summary (period mean 2015-2022, kg O2-eq/yr, NOx+NH3):")
print(summ.round(1).to_string(index=False))

order = [s for s, _ in SITES]
pm["site"] = pd.Categorical(pm["site"], order)
pm = pm.sort_values(["site", "old"], ascending=[True, False])
try:
    with pd.ExcelWriter(OUT + ".xlsx", engine="openpyxl") as w:
        pm.to_excel(w, sheet_name="Period mean", index=False)
        g.sort_values(["site", "year", "old"], ascending=[True, True, False]) \
         .to_excel(w, sheet_name="By year", index=False)
        summ.to_excel(w, sheet_name="Site summary", index=False)
        (chk if not chk.empty else pd.DataFrame({"status": ["no unexpected sector changed"]})
         ).to_excel(w, sheet_name="Check", index=False)
    print(f"\nwritten -> {OUT}.xlsx")
except ImportError:
    for name, df in [("period_mean", pm), ("by_year", g), ("site_summary", summ), ("check", chk)]:
        df.to_csv(f"{OUT}_{name}.csv", index=False)
    print(f"\nopenpyxl missing -> wrote {OUT}_*.csv instead")
