# F_6_build_database.py - long-format database of the satellite, old vs anchored
# ---------------------------------------------------------------------------
# One tidy table per pathway (NOx, NH3, Nleach), all 305 cLME sub-segments:
#   year | path | LME | climate | country | sector |
#   eutrophication_kgO2 (original) | anchored_kgO2 (GLORIA-anchored batch)
# Climate zones (Polar / Subpolar / Temperate / Subtropical / Tropical) come
# from Supplementary Table S1. Nleach is identical in both batches by design.
#
# ONE YEAR at a time (plain csv, easier to handle; ~6M rows / ~600 MB for NOx).
#
# RUN (from F_Practical_case, after 2_make_anchored_satellites.py):
#   python F_6_build_database.py            -> year 2015 (default)
#   python F_6_build_database.py 2018       -> any other year
# OUTPUT -> "1. results/F6_database/F6_database_<path>_<year>.csv"
# ---------------------------------------------------------------------------
import os
import sys
import numpy as np
import pandas as pd
import scipy.sparse as sp

HERE = os.path.dirname(os.path.abspath(__file__))
EM   = os.path.join(HERE, "..", "E_MRIO_GLORIA_Satellites")
OLD  = os.path.join(EM, "1. GLORIAv60_Eutrophication_Satellites")
NEW  = os.path.join(EM, "1b. GLORIAv60_Eutrophication_Satellites_anchored")
OUTD = os.path.join(HERE, "1. results", "F6_database")
os.makedirs(OUTD, exist_ok=True)
YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2015
YEARS = [YEAR]

# ---- labels: rows -> LME, columns -> (country, sector) ----------------------
rows = pd.read_csv(os.path.join(OLD, "satellite_row_labels.csv"))
RC   = "LME_nb_f_1" if "LME_nb_f_1" in rows.columns else rows.columns[-1]
LME  = rows[RC].astype(str).values
lab  = pd.read_csv(os.path.join(OLD, "satellite_column_labels.csv"))
CTY  = lab["region"].astype(str).values
SEC  = np.array([l.split(f"({r}) ", 1)[-1].removesuffix(" industry").removesuffix(" product")
                 for l, r in zip(lab["label"], lab["region"])])

# ---- climate zone per sub-segment, from Supplementary Table S1 --------------
S1 = pd.read_excel(os.path.join(HERE, "SI_2_Supplementary Table.xlsx"),
                   sheet_name="Table S1", header=2)
S1["seg"] = S1["# Subsegment"].astype(str).str.strip()
S1["zone"] = S1["Cliamte Zone"].astype(str).str.strip()
# KNOWN Table S1 defect: the 'X_10' rows are typed as 'X_1' (trailing zero
# lost), which duplicates 'X_1'. The second occurrence is repaired to 'X_10'
# here for the join - but fix the xlsx itself before publication.
zmap, repaired = {}, []
for seg, zone in zip(S1["seg"], S1["zone"]):
    if seg in zmap and seg.endswith("_1") and (seg + "0") not in zmap:
        zmap[seg + "0"] = zone
        repaired.append(seg + "0")
    else:
        zmap[seg] = zone
if repaired:
    print("Table S1 repair: duplicated 'X_1' rows read as", ", ".join(repaired),
          "- correct the xlsx itself before publishing it.")
def climate(lme):
    return zmap.get(lme) or zmap.get(lme + "_0") or \
           (zmap.get(lme[:-2]) if lme.endswith("_0") else None) or "Unknown"
CLIM = np.array([climate(v) for v in LME])
n_unk = int((CLIM == "Unknown").sum())
if n_unk:
    print(f"note: {n_unk} sub-segment(s) without a climate zone in Table S1 -> 'Unknown'")

# ---- build: per pathway, append year by year (constant memory) --------------
for PATH in ["NOx", "NH3", "Nleach"]:
    out = os.path.join(OUTD, f"F6_database_{PATH}_{YEAR}.csv")
    if os.path.exists(out):
        os.remove(out)
    first, nrows = True, 0
    for Y in YEARS:
        fo = os.path.join(OLD, f"satellite_{PATH}_{Y}.npz")
        fn = os.path.join(NEW, f"satellite_{PATH}_{Y}.npz")
        if not (os.path.exists(fo) and os.path.exists(fn)):
            print(f"{PATH} {Y}: satellite missing in one batch - skipped"); continue
        a = sp.load_npz(fo).tocoo()
        b = sp.load_npz(fn).tocoo()
        d = (pd.DataFrame({"r": a.row, "c": a.col, "eutrophication_kgO2": a.data})
               .merge(pd.DataFrame({"r": b.row, "c": b.col, "anchored_kgO2": b.data}),
                      on=["r", "c"], how="outer")
               .fillna({"eutrophication_kgO2": 0.0, "anchored_kgO2": 0.0}))
        rix = d.pop("r").values.astype(int)
        cix = d.pop("c").values.astype(int)
        d.insert(0, "year", Y)
        d.insert(1, "path", PATH)
        d.insert(2, "LME", LME[rix])
        d.insert(3, "climate", CLIM[rix])
        d.insert(4, "country", CTY[cix])
        d.insert(5, "sector", SEC[cix])
        d = d[["year", "path", "LME", "climate", "country", "sector",
               "eutrophication_kgO2", "anchored_kgO2"]]
        d.to_csv(out, index=False, header=first, mode="a" if not first else "w",
                 float_format="%.6e")
        first = False
        nrows += len(d)
        print(f"{PATH} {Y}: {len(d):,} rows")
    if nrows:
        print(f"{PATH}: TOTAL {nrows:,} rows -> {out} "
              f"({os.path.getsize(out)/1e6:.0f} MB)\n")
print("done")
