# F_5_sector_tables_from_satellite.py - Fig. 3 inputs straight from the satellites
# ---------------------------------------------------------------------------
# PBA is the satellite row (verified: E_1's *_production_full.csv reproduces the
# satellite row to 1e-16), so the per-reef sector tables behind Fig. 3 need no
# MATLAB. This writes, for every substance / year / site, the same file E_1
# exports:  {SUB}_{YEAR}_{site}_production_full.csv
#           (producer_region, sector, kgO2, share_of_LME)
#
# RUN (from F_Practical_case):
#   python F_5_sector_tables_from_satellite.py                 all years, original batch
#   python F_5_sector_tables_from_satellite.py 2018            one year
#   python F_5_sector_tables_from_satellite.py anchored        GLORIA-anchored batch:
#       reads "1b. ..._anchored", writes to "1. results_anchored/PBA", and adds
#       two pseudo-sector rows per producer from the delta satellites -
#       "Water transport - international (unassigned)" and
#       "Road transport - household" - so Fig. 3 can show the split.
# What still needs E_1: the full 305-sub-segment CBA/PBA tables (Fig. 2, the
# global results, FP_all_years_long). The Sankeys never needed it - F_4
# recomputes the producer x consumer matrix itself from satellite + x_cty.
# ---------------------------------------------------------------------------
import os
import sys
import numpy as np
import pandas as pd
import scipy.sparse as sp

ANCH  = any(a.lower() == "anchored" for a in sys.argv[1:])
YEARS = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(2015, 2023))

HERE    = os.path.dirname(os.path.abspath(__file__))
SAT_DIR = os.path.join(HERE, "..", "E_MRIO_GLORIA_Satellites",
                       "1b. GLORIAv60_Eutrophication_Satellites_anchored" if ANCH
                       else "1. GLORIAv60_Eutrophication_Satellites")
OUT_DIR = os.path.join(HERE, "1. results_anchored" if ANCH else "1. results", "PBA")
os.makedirs(OUT_DIR, exist_ok=True)

SITES = ["10", "12_1", "12_2", "36_13", "36_18", "49", "40_4"]
DELTA = {"dship": "Water transport - international (unassigned)",
         "dhh":   "Road transport - household"}

rows = pd.read_csv(os.path.join(SAT_DIR, "satellite_row_labels.csv"))
RC   = "LME_nb_f_1" if "LME_nb_f_1" in rows.columns else rows.columns[-1]
ridx = {}
for s in SITES:
    hit = rows.index[rows[RC].astype(str).isin([s, s + "_0"])]
    if len(hit):
        ridx[s] = int(hit[0])
lab = pd.read_csv(os.path.join(SAT_DIR, "satellite_column_labels.csv"))
lab["sector"] = [l.split(f"({r}) ", 1)[-1].removesuffix(" industry").removesuffix(" product")
                 for l, r in zip(lab["label"], lab["region"])]

for SUB in ["NOx", "NH3", "Nleach"]:
    for Y in YEARS:
        satf = os.path.join(SAT_DIR, f"satellite_{SUB}_{Y}.npz")
        if not os.path.exists(satf):
            continue
        S = sp.load_npz(satf).tocsr()
        D = {}
        if ANCH and SUB in ("NOx", "NH3"):
            for k in DELTA:
                f = os.path.join(SAT_DIR, f"satellite_{k}_{SUB}_{Y}.npz")
                if os.path.exists(f):
                    D[k] = sp.load_npz(f).tocsr()
        for site, ri in ridx.items():
            q = np.asarray(S[ri].todense()).ravel()
            t = (lab.assign(kgO2=q)[lambda d: d.kgO2 > 0]
                    .groupby(["region", "sector"], as_index=False)["kgO2"].sum()
                    .rename(columns={"region": "producer_region"}))
            for k, name in DELTA.items():                  # anchored: the two flows
                if k not in D:
                    continue
                qd = np.asarray(D[k][ri].todense()).ravel()
                if qd.sum() <= 0:
                    continue
                e = (lab.assign(kgO2=qd)[lambda d: d.kgO2 > 0]
                        .groupby("region", as_index=False)["kgO2"].sum()
                        .rename(columns={"region": "producer_region"}))
                e["sector"] = name
                t = pd.concat([t, e[["producer_region", "sector", "kgO2"]]],
                              ignore_index=True)
            if t.empty:
                continue
            t["share_of_LME"] = t.kgO2 / t.kgO2.sum()
            t = t.sort_values("kgO2", ascending=False)
            t.to_csv(os.path.join(OUT_DIR, f"{SUB}_{Y}_{site}_production_full.csv"),
                     index=False)
        print(f"{SUB} {Y}: sector tables written for {len(ridx)} sites"
              + (f" (+{'/'.join(k for k in D)} pseudo-sectors)" if D else ""))
print("->", OUT_DIR)
