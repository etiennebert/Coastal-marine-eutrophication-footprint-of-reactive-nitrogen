# -*- coding: utf-8 -*-
"""
apply_NH3_CF_country_LME.py
Atmospheric NH3 -> marine eutrophication, detailed per YEAR x IPCC sector x
EMISSION COUNTRY x LME.   (identical machinery to the NOx version)

  emission cell -> COUNTRY via EEZ-land union (SOVEREIGN1); over-water emissions
                   keep a country, open ocean -> 'High seas (ABNJ)'.
  receptor cell -> LME via the area-weighted spatial mapping.
  CF applied as the full source->receptor matrix, collapsed once: CF_to_LME = CF @ M.

NOTE: CF_NHx is per kg NH3 EMITTED (the MATLAB normalises by emission_nhx), so EDGAR
NH3 is fed straight in (tonnes -> kg), no N conversion -- exactly as for NOx.
Requires: numpy, pandas, geopandas, rasterio.
"""
import numpy as np, pandas as pd, geopandas as gpd
from rasterio import features
from rasterio.transform import from_origin

import os
try:
    NH3_DIR = os.path.dirname(os.path.abspath(__file__))   # B_airborne_NH3 folder
except NameError:
    NH3_DIR = os.getcwd()
EDGAR   = NH3_DIR + r"\NH3_EDGAR_2015_2022.csv"          # <-- you provide (same columns as NOx)
CF_FILE = NH3_DIR + r"\CF_NHx_all.csv"                    # <-- you provide (run CF_NHx.m)
MAP_FILE= NH3_DIR + r"\0_gridcells_LME_mapped.csv"        # reused (copied)
EEZ_SHP = NH3_DIR + r"\EEZ_land_union_v3_202003\EEZ_Land_v3_202030.shp"   # reused (copied)
OUT_MAIN= NH3_DIR + r"\NH3_impact_country_to_LME.csv"
OUT_COUN= NH3_DIR + r"\NH3_impact_by_country_sector.csv"
OUT_LME = NH3_DIR + r"\NH3_impact_by_LME_sector.csv"

NLAT, NLON = 91, 144
N = NLAT * NLON
TONNES_TO_KG = 1.0e3
COUNTRY_FIELD = "SOVEREIGN1"

# 1) rasterize EEZ-land union -> 0.1 deg country-index grid
g = gpd.read_file(EEZ_SHP)
sov = g[COUNTRY_FIELD].fillna("High seas (ABNJ)").values
tr = from_origin(-180, 90, 0.1, 0.1)
rast = features.rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)),
                          out_shape=(1800, 3600), transform=tr, fill=0, dtype="int32")

# 2) read EDGAR in CHUNKS -> air-cell z + emission country -> bin
parts = []
for df in pd.read_csv(EDGAR, usecols=["Year", "lat", "lon", "IPCC", "emission"], chunksize=5_000_000):
    lat = df["lat"].values; lon = df["lon"].values
    a = np.clip(np.floor((lat + 90) * NLAT / 180).astype(int), 0, NLAT - 1)
    b = np.clip(np.floor((lon + 180) * NLON / 360).astype(int), 0, NLON - 1)
    z = a * NLON + b
    rr = np.clip(((90 - lat) / 0.1).astype(int), 0, 1799); ccol = np.clip(((lon + 180) / 0.1).astype(int), 0, 3599)
    pidx = rast[rr, ccol] - 1
    country = np.where(pidx < 0, "High seas (ABNJ)", sov[np.clip(pidx, 0, None)]).astype(object)
    parts.append(pd.DataFrame({"year": df["Year"].values, "sector": df["IPCC"].values, "z": z,
                 "country": country, "emis_kg": df["emission"].values * TONNES_TO_KG})
                 .groupby(["year", "sector", "z", "country"], as_index=False)["emis_kg"].sum())
E = (pd.concat(parts, ignore_index=True)
       .groupby(["year", "sector", "z", "country"], as_index=False)["emis_kg"].sum())

# 3) receptor->LME area-weights, then CF_to_LME = CF @ M (single chunked CF pass)
m = pd.read_csv(MAP_FILE)
m["w"] = m["AreaSqKm"] / m.groupby("Cell_ID")["AreaSqKm"].transform("sum")
labels = np.array(sorted(m["LME_nb_f_1"].unique())); Ln = len(labels)
lme_idx = {k: i for i, k in enumerate(labels)}
M = np.zeros((N, Ln), dtype=np.float32)
for cid, lme, w in zip(m["Cell_ID"].values, m["LME_nb_f_1"].values, m["w"].values):
    M[cid - 1, lme_idx[lme]] += w
# --- per-year emission vector over source air cells (for the per-receptor-cell map) ---
years_sorted = sorted(E["year"].unique())
evec_year = {Y: np.zeros(N) for Y in years_sorted}
for Y in years_sorted:
    _sub = E[E["year"] == Y]
    np.add.at(evec_year[Y], _sub["z"].values.astype(int), _sub["emis_kg"].values)
cell_impact_year = {Y: np.zeros(N) for Y in years_sorted}   # impact per RECEPTOR cell, per year
colsum = np.zeros(N)   # per-receptor CF = sum over sources of CF(z,j)
CFL = np.zeros((N, Ln)); rowsum = np.zeros(N); r0 = 0
for ch in pd.read_csv(CF_FILE, header=None, dtype=np.float32, chunksize=2000):
    blk = ch.values; k = blk.shape[0]
    CFL[r0:r0 + k] = blk @ M
    rowsum[r0:r0 + k] = blk.sum(axis=1)   # total kg O2 per kg emitted over ALL receptors (mapped+inland)
    for Y in years_sorted:                    # receptor impact_Y(j) = sum_z emis_Y(z)*CF(z,j)
        cell_impact_year[Y] += evec_year[Y][r0:r0 + k] @ blk
    colsum += blk.sum(axis=0)
    r0 += k

# 4) combine -> impact per (year, sector, country, LME) + marginals
zc = E["z"].values; emis = E["emis_kg"].values
contrib = emis[:, None] * CFL[zc]
yc, yu = pd.factorize(E["year"]); sc, su = pd.factorize(E["sector"]); cc, cu = pd.factorize(E["country"])
gcomb = (yc.astype(np.int64) * len(su) + sc) * len(cu) + cc
gu, inv = np.unique(gcomb, return_inverse=True); G = len(gu)
impact_gL = np.zeros((G, Ln)); np.add.at(impact_gL, inv, contrib)
emis_g = np.bincount(inv, weights=emis, minlength=G)
cci = gu % len(cu); rem = gu // len(cu); sci = rem % len(su); yci = rem // len(su)
yr = yu[yci]; sek = su[sci]; cou = cu[cci]
gg, ll = np.nonzero(impact_gL > 0.0)
main = pd.DataFrame({"year": yr[gg], "IPCC_sector": sek[gg], "emission_country": cou[gg],
                     "LME_nb_f_1": labels[ll], "impact_kgO2": impact_gL[gg, ll], "emission_kg": emis_g[gg], "CF_kgO2_per_kg": impact_gL[gg, ll] / emis_g[gg]}) \
         .sort_values(["year", "emission_country", "impact_kgO2"], ascending=[True, True, False])
main.to_csv(OUT_MAIN, index=False)
pd.DataFrame({"year": yr, "IPCC_sector": sek, "emission_country": cou,
             "emission_kgNH3": emis_g, "impact_kgO2_caused": impact_gL.sum(1)}) \
   .sort_values(["year", "impact_kgO2_caused"], ascending=[True, False]).to_csv(OUT_COUN, index=False)
main.groupby(["year", "IPCC_sector", "LME_nb_f_1"], as_index=False)["impact_kgO2"].sum().to_csv(OUT_LME, index=False)
print("GLOBAL NH3 impact (country-attributed) = %.4e kg O2" % main["impact_kgO2"].sum())
print("rows: country_to_LME=%d  by_country_sector=%d" % (len(main), G))

# ---- inland (unmapped) gap: coastal-mapped LMEs vs ALL receptors ----
allimp = E["emis_kg"].values * rowsum[E["z"].values]
tot_all = allimp.sum(); tot_map = main["impact_kgO2"].sum()
print("mapped (coastal) impact : %.4e kg O2 (%.1f%% of all-receptor impact)" % (tot_map, 100*tot_map/tot_all))
print("inland (unmapped) gap   : %.4e kg O2 (%.1f%%)" % (tot_all-tot_map, 100*(tot_all-tot_map)/tot_all))
Eg = pd.DataFrame({"year": E["year"].values, "all": allimp}).groupby("year")["all"].sum()
mby = main.groupby("year")["impact_kgO2"].sum()
for _y in Eg.index:
    print("   year %d: mapped %.1f%%  inland %.1f%%" % (_y, 100*mby.get(_y,0)/Eg[_y], 100*(Eg[_y]-mby.get(_y,0))/Eg[_y]))

# ---- per-receptor-cell impact map, one file per year (mirrors agricultural per-cell outputs) ----
zz = np.arange(N)
LAT = (zz // NLON + 0.5) * 180.0 / NLAT - 90.0
LON = (zz %  NLON + 0.5) * 360.0 / NLON - 180.0
_dom = (m.sort_values("AreaSqKm", ascending=False)
          .drop_duplicates("Cell_ID").set_index("Cell_ID")["LME_nb_f_1"])
lme_of_cell = pd.Series(zz + 1).map(_dom).values          # dominant LME sub-segment per cell
mapped_cell = ~pd.isna(lme_of_cell)
for Y in years_sorted:
    cdf = pd.DataFrame({"year": Y, "Cell_ID": zz + 1, "lat": LAT, "lon": LON,
                        "LME_nb_f_1": lme_of_cell, "mapped": mapped_cell,
                        "impact_kgO2": cell_impact_year[Y]})
    cdf = cdf[cdf["impact_kgO2"] > 0]
    cdf.to_csv(os.path.join(NH3_DIR, "NH3_impact_per_cell_%d.csv" % Y), index=False)
    _tot = cdf["impact_kgO2"].sum(); _mp = cdf.loc[cdf["mapped"], "impact_kgO2"].sum()
    print("per-cell %d: %d cells, total %.4e kg O2 (mapped coastal %.1f%%)" % (Y, len(cdf), _tot, 100*_mp/_tot if _tot else 0))
print("per-cell impact maps -> NH3_impact_per_cell_<year>.csv")

# ---- effective CF summaries (keep the CF, like the agricultural CF layer) ----
CF_LME = CFL.sum(axis=0)   # kg O2 in each LME per kg emitted, summed over all source cells
pd.DataFrame({"LME_nb_f_1": labels, "CF_sum_over_sources": CF_LME,
              "CF_mean_per_source": CF_LME / float(N)}).to_csv(os.path.join(NH3_DIR, "NH3_CF_by_LME.csv"), index=False)
_cfmap = pd.DataFrame({"Cell_ID": zz + 1, "lat": LAT, "lon": LON, "LME_nb_f_1": lme_of_cell,
                       "mapped": mapped_cell, "CF_kgO2_per_kg": colsum})
_cfmap = _cfmap[_cfmap["CF_kgO2_per_kg"] > 0]
_cfmap.to_csv(os.path.join(NH3_DIR, "NH3_CF_receptor_map.csv"), index=False)
print("CF summaries -> NH3_CF_by_LME.csv (per LME), NH3_CF_receptor_map.csv (per cell)")
