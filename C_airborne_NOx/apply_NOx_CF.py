# -*- coding: utf-8 -*-
"""
apply_NOx_CF.py  --  atmospheric NOx -> marine eutrophication, per LME

Flat chain, one step after another:
  1) EDGAR NOx (0.1 deg cells, tonnes NO2) -> sum IPCC sectors -> regrid onto the
     91x144 air grid.  The air grid is the EXACT 'equal split' grid of
     gridcells_coord.py:  lat band = 180/91 deg, SOUTH-first;  lon band = 2.5 deg,
     WEST-first;  z = a*144 + b (0-based);  Cell_ID = z + 1.
  2) impact[j] = sum_i emission[i] * CF[i,j]
     CF = CF_NOx_all (13104 x 13104): row i = EMISSION cell, col j = RECEPTOR
     ('ending') cell, value = kg O2 per kg NO2 emitted.  Read in row-chunks so we
     never hold the whole 2.5 GB matrix in RAM.
  3) aggregate impact to LME using the student's spatial match
     0_gridcells_LME_mapped.csv  (air cell  n  cLME_ss_full.shp), area-weighted.
  4) report how much impact lands in UNMAPPED (inland) cells = the land-routed gap.
"""
import numpy as np, pandas as pd

import os
try:
    NOX_DIR = os.path.dirname(os.path.abspath(__file__))   # C_airborne_NOx folder
except NameError:
    NOX_DIR = os.getcwd()
EDGAR    = NOX_DIR + r"\NOx_EDGAR.csv"
CF_FILE  = NOX_DIR + r"\CF_NOx_all.csv"
MAP_FILE = NOX_DIR + r"\0_gridcells_LME_mapped.csv"
OUT_CELL = NOX_DIR + r"\NOx_impact_per_receptor_cell.csv"
OUT_LME  = NOX_DIR + r"\NOx_impact_per_LME.csv"
OUT_IN   = NOX_DIR + r"\NOx_impact_unmapped_inland_cells.csv"

NLAT, NLON = 91, 144
N = NLAT * NLON                 # 13104
TONNES_TO_KG = 1.0e3
CHUNK = 1000                    # CF rows per chunk

# air-grid index, matching gridcells_coord.py EXACTLY (equal split, S-first, W-first)
def z_index(lat, lon):
    a = np.clip(np.floor((lat + 90.0)  * NLAT / 180.0).astype(int), 0, NLAT - 1)   # 0..90  S->N
    b = np.clip(np.floor((lon + 180.0) * NLON / 360.0).astype(int), 0, NLON - 1)   # 0..143 W->E
    return a * NLON + b                                                            # Cell_ID = z+1

zz  = np.arange(N)
LAT = (zz // NLON + 0.5) * 180.0 / NLAT - 90.0
LON = (zz %  NLON + 0.5) * 360.0 / NLON - 180.0

# ---- 1) EDGAR -> emission vector (kg NO2 per air cell) --------------------------
e = pd.read_csv(EDGAR, usecols=["lat", "lon", "emission"])
e = e.groupby(["lat", "lon"], as_index=False)["emission"].sum()
z = z_index(e["lat"].values, e["lon"].values)
evec = np.zeros(N)
np.add.at(evec, z, e["emission"].values * TONNES_TO_KG)
print("EDGAR total: %.1f Tg NO2/yr" % (evec.sum() / 1e9))
top = np.argsort(evec)[::-1][:8]
print("top-emitting air cells (should be China / Europe / US / India):")
for k in top:
    print("   lat %6.1f  lon %7.1f   %.2f Tg" % (LAT[k], LON[k], evec[k] / 1e9))

# ---- 2) impact = evec @ CF  (row-chunked) --------------------------------------
impact = np.zeros(N); r0 = 0
for chunk in pd.read_csv(CF_FILE, header=None, dtype=np.float32, chunksize=CHUNK):
    blk = chunk.values
    impact += evec[r0:r0 + blk.shape[0]] @ blk
    r0 += blk.shape[0]
print("CF rows processed:", r0, "(expect 13104)")
print("GLOBAL atmospheric NOx eutrophication: %.3e kg O2" % impact.sum())

pd.DataFrame({"Cell_ID": zz + 1, "lat": LAT, "lon": LON,
              "impact_kgO2": impact}).to_csv(OUT_CELL, index=False)

# ---- 3) aggregate to LME via the spatial mapping (area-weighted within each cell)
m = pd.read_csv(MAP_FILE)
m["w"] = m["AreaSqKm"] / m.groupby("Cell_ID")["AreaSqKm"].transform("sum")
m["impact_kgO2"] = impact[m["Cell_ID"].values - 1] * m["w"]
per_lme = (m.groupby("LME_nb_f_1", as_index=False)["impact_kgO2"].sum()
             .sort_values("impact_kgO2", ascending=False))
per_lme.to_csv(OUT_LME, index=False)
print("wrote per-LME ->", OUT_LME, "(", len(per_lme), "LMEs )")

# ---- 4) inland (unmapped) gap --------------------------------------------------
mapped = np.zeros(N, bool); mapped[np.unique(m["Cell_ID"].values) - 1] = True
tot = impact.sum()
print("impact in mapped COASTAL  cells: %.3e kg O2 (%.1f%%)" %
      (impact[mapped].sum(),  100 * impact[mapped].sum()  / tot))
print("impact in UNMAPPED INLAND cells: %.3e kg O2 (%.1f%%)" %
      (impact[~mapped].sum(), 100 * impact[~mapped].sum() / tot))
inl = pd.DataFrame({"Cell_ID": (zz + 1)[~mapped], "lat": LAT[~mapped],
                    "lon": LON[~mapped], "impact_kgO2": impact[~mapped]})
inl[inl["impact_kgO2"] > 0].to_csv(OUT_IN, index=False)
print("wrote unmapped inland cells ->", OUT_IN)
