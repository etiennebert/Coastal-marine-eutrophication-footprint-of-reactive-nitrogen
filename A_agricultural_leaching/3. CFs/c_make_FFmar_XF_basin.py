# c_make_FFmar_XF_basin.py - per-BASIN marine tail (XF / removal) for delivered-N
# ---------------------------------------------------------------------------
# Builds, in "3. CFs":
#   FFmar_XF_basin.csv       BasinID | FFmar_XF | XF | removal_final | cLME_ss | n_cells
#   FFmar_XF_subsegment.csv  LME_nb_f_1 | FFmar_XF_ss | n_basins     (fallback for the
#                            small basins absent from the 2-deg air-grid tables)
# so the leaching pipelines can compute, per 5-arcmin cell,
#     Fraction_N_marine = CF / FFmar_XF   (clipped at 1)     and
#     N_reaching        = leaching * Fraction_N_marine.
#
# SOURCE  Model input/SOS_airgrid.xls - the table the ARABLE chain itself was built
# from: it holds FE_arable and FF_arable_final per air cell, and the identity
# FF_arable_final = FE_arable / removal_final (median ratio 1.00000) shows the
# marine fate factor used for CF_arable is 1/removal_final (the effective residence
# time). The tail is therefore  FFmar_XF = XF__kg_O2_kg_N_ / removal_final,
# essentially unique per basin in this table (4 of 1,899 basins carry two removal
# values -> median, reported). VALIDATED against cell_attributes_static.csv:
# CF/tail saturates at 1 (p99 = 0.99) with this vintage; the FF_mar_inland vintage
# (updated XF) does NOT match CF_arable and is no longer used.
#
# RUN from "A_agricultural_leaching/3. CFs":  python c_make_FFmar_XF_basin.py
#   optional argument = path to the "Model input" folder if not auto-found.
# Needs: pandas, xlrd (pip install xlrd).
# ---------------------------------------------------------------------------
import os
import sys
import numpy as np
import pandas as pd

try:
    HERE = os.path.dirname(os.path.abspath(__file__))          # ...\3. CFs
except NameError:
    HERE = os.getcwd()
A_DIR = os.path.dirname(HERE)                                  # ...\A_agricultural_leaching
ROOT  = os.path.dirname(A_DIR)                                 # ...\Supporting_Information / model root

CAND = ([sys.argv[1]] if len(sys.argv) > 1 else []) + [
    os.path.join(ROOT, "C_airborne_NOx", "2. CFs", "Model input"),
    os.path.join(ROOT, "CFs Model input"),
    os.path.join(HERE, "CFs Model input")]
MODELIN = next((c for c in CAND if os.path.exists(os.path.join(c, "SOS_airgrid.xls"))), None)
if MODELIN is None:
    raise SystemExit("SOS_airgrid.xls not found; tried: " + "; ".join(CAND))
print("CFs Model input ->", MODELIN)

# ---- 1) SOS air-grid table: the arable chain's own ingredients --------------
t = pd.read_excel(os.path.join(MODELIN, "SOS_airgrid.xls"))
t = t.dropna(subset=["removal_final", "XF__kg_O2_kg_N_", "BasinID"]).copy()
t = t[t["removal_final"] > 0]
t["BasinID"] = t["BasinID"].astype(int)
t["tail"] = t["XF__kg_O2_kg_N_"] / t["removal_final"]
print("rows:", len(t), "| basins:", t["BasinID"].nunique())

# sanity: the construction rule of the arable fate factor must hold in this table
chk = t.dropna(subset=["FE_arable", "FF_arable_final"])
chk = chk[chk["FE_arable"] > 0]
r = (chk["FF_arable_final"] * chk["removal_final"] / chk["FE_arable"]).median()
print("identity FF_arable_final = FE_arable / removal_final: median ratio %.5f (must be ~1)" % r)

# ---- 2) one tail per basin (median; >1 removal value in only a handful) -----
out = (t.groupby("BasinID")
         .agg(FFmar_XF=("tail", "median"), XF=("XF__kg_O2_kg_N_", "first"),
              removal_final=("removal_final", "median"), cLME_ss=("LME_nb_final", "first"),
              n_cells=("tail", "size"), n_rem=("removal_final", "nunique"))
         .reset_index())
print("basins with >1 removal value (median used):", int((out["n_rem"] > 1).sum()))
out = out.drop(columns="n_rem")
print("FFmar_XF (kg O2 per kg N entering the water): min %.3g | median %.3g | max %.3g"
      % (out["FFmar_XF"].min(), out["FFmar_XF"].median(), out["FFmar_XF"].max()))
out.to_csv(os.path.join(HERE, "FFmar_XF_basin.csv"), index=False)

# ---- 3) sub-segment fallback: median tail of the sub-segment's basins -------
#   ~20% of the 5-arcmin CF cells drain through small basins that never resolved
#   on the 2-deg air grid; the pipelines fall back to their sub-segment's tail.
ss = (out.dropna(subset=["cLME_ss"])
         .groupby("cLME_ss")
         .agg(FFmar_XF_ss=("FFmar_XF", "median"), n_basins=("FFmar_XF", "size"))
         .reset_index().rename(columns={"cLME_ss": "LME_nb_f_1"}))
ss.to_csv(os.path.join(HERE, "FFmar_XF_subsegment.csv"), index=False)
print("written -> FFmar_XF_basin.csv (%d basins) + FFmar_XF_subsegment.csv (%d sub-segments)"
      % (len(out), len(ss)))
