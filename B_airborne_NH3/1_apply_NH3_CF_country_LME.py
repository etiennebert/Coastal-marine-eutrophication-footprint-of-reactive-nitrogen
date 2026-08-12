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
# ---------------------------------------------------------------------------
# PIPELINE OVERVIEW  (documented in the same review style as the agricultural scripts;
#                     '# %%' cells -> run step by step in Spyder, top to bottom)
#   1) EEZ-land union -> 0.1 deg COUNTRY grid                    (who emitted)
#   2) EDGAR 0.1 deg points -> emitter country + CF-grid cell z  -> DB1
#   3) receptor cells -> LME weights M; ONE streamed pass over the
#      13,104 x 13,104 CF matrix:  CF_to_LME = CF @ M            -> DB2 (per year)
#   4) eutrophication per (year, sector, emitter country) x LME  -> main tables
#   5) inland-gap check, per-receptor-cell maps, aggregate CF layers
#   6) A5e: LME -> receptor-country split (validated EEZ coverage shares)
#
# THREE GRIDS -- keep them apart while reviewing:
#   0.1 deg (3600x1800): EDGAR emissions + the rasterized country layer;
#   ~2 x 2.5 deg (91x144 = 13,104 cells, flat id z; 1-based Cell_ID in outputs):
#       the atmospheric CF grid. CAREFUL: z counts row 0 from the SOUTH pole
#       ((lat+90) ascending) -- the OPPOSITE of the agricultural fid (90-lat);
#   vector LME sub-segments (labels like '22_3'; single-segment LMEs appear as 'X_0').
# ---------------------------------------------------------------------------
# %% imports + paths  (nothing to edit - every path is relative to THIS file)
import numpy as np, pandas as pd, geopandas as gpd
from rasterio import features
from rasterio.transform import from_origin

import os
try:
    NH3_DIR = os.path.dirname(os.path.abspath(__file__))   # B_airborne_NH3 folder
except NameError:
    NH3_DIR = os.getcwd()
# ---- INPUT / OUTPUT locations (rename-proof: the first existing candidate wins) ----
#   Shared layers live in ..\0_shape_files (common to agriculture and BOTH air scripts);
#   per-pathway data sit in the numbered subfolders; every output goes to "3. Output".
def _first(cands, what):
    for c in cands:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(what + " not found; tried:\n  " + "\n  ".join(cands))
SHAPES  = os.path.join(os.path.dirname(NH3_DIR), "0_shape_files")
EDGAR   = _first([os.path.join(NH3_DIR, "NH3_EDGAR_2015_2022.parquet"),   # compact db (0_prepare_EDGAR_emissions.py)
                  os.path.join(NH3_DIR, "NH3_EDGAR_2015_2022.csv"),       # legacy csv at the folder root
                  os.path.join(NH3_DIR, "1. EDGARv8.1_NH3emissions", "NH3_EDGAR_2015_2022.csv"),   # ...or moved next to the raw files
                  os.path.join(NH3_DIR, "0. Old", "NH3_EDGAR_2015_2022.csv")],   # ...or archived
                 "EDGAR NH3 database")
CF_FILE = _first([os.path.join(NH3_DIR, "2. CFs", "CF_NHx_all.csv"),
                  os.path.join(NH3_DIR, "CF_NHx_all.csv")], "CF_NHx_all.csv")
MAP_FILE= _first([os.path.join(SHAPES, "0_gridcells_LME_mapped.csv"),          # SHARED copy
                  os.path.join(NH3_DIR, "0_gridcells_LME_mapped.csv")], "0_gridcells_LME_mapped.csv")
EEZ_SHP = _first([os.path.join(SHAPES, "6_EEZ_land_union_v3_202003", "EEZ_Land_v3_202030.shp"),   # SHARED copy
                  os.path.join(NH3_DIR, "EEZ_land_union_v3_202003", "EEZ_Land_v3_202030.shp")],
                 "EEZ_Land_v3_202030.shp")
NH3_OUT = os.path.join(NH3_DIR, "3. Output")
# outputs sorted into 5 subfolders (created on the fly):
OUT_TABLES = os.path.join(NH3_OUT, "1_impact_tables")       # country x sector x LME + the two marginals
OUT_DB     = os.path.join(NH3_OUT, "2_databases")           # DB1 (emissions) and DB2 (cell -> LME)
OUT_RECEPT = os.path.join(NH3_OUT, "3_receptor_countries")  # A5e LME -> receptor-country split
OUT_CELLS  = os.path.join(NH3_OUT, "4_per_cell_maps")       # receptor-cell impact, one file per year
OUT_CF     = os.path.join(NH3_OUT, "5_CF_layers")           # aggregate CF summaries
for _d in (NH3_OUT, OUT_TABLES, OUT_DB, OUT_RECEPT, OUT_CELLS, OUT_CF):
    os.makedirs(_d, exist_ok=True)
OUT_MAIN= os.path.join(OUT_TABLES, "NH3_impact_country_to_LME.csv")
OUT_COUN= os.path.join(OUT_TABLES, "NH3_impact_by_country_sector.csv")
OUT_LME = os.path.join(OUT_TABLES, "NH3_impact_by_LME_sector.csv")
print("input db:", os.path.basename(EDGAR), "| outputs ->", NH3_OUT)

NLAT, NLON = 91, 144
N = NLAT * NLON
TONNES_TO_KG = 1.0e3
COUNTRY_FIELD = "SOVEREIGN1"

# %% 1) GEO-STEP 1 of 2 : rasterize the EEZ-land union -> 0.1 deg COUNTRY-index grid
#   WHY : tags every emission with its EMITTER country. The EEZ-LAND UNION (not a land-only
#         map) is used so over-water emissions - shipping lanes, offshore platforms - still
#         belong to a coastal state's zone; only true open ocean falls outside every polygon.
#   HOW : polygon k is burnt as the integer k+1 into a 1800x3600 grid (0.1 deg; row 0 at 90N,
#         col 0 at 180W). fill=0 marks 'no polygon', so after the -1 shift in step 2,
#         pidx < 0  ==  open ocean  ->  'High seas (ABNJ)'.
#   NOTE: rasterizing ONCE replaces ~80M point-in-polygon tests; at 0.1 deg the worst border
#         error (~5 km) is far below the ~2 deg CF grid this feeds.
g = gpd.read_file(EEZ_SHP)
sov = g[COUNTRY_FIELD].fillna("High seas (ABNJ)").values
tr = from_origin(-180, 90, 0.1, 0.1)
rast = features.rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)),
                          out_shape=(1800, 3600), transform=tr, fill=0, dtype="int32")

# %% 2) GEO-STEP 2 of 2 : EDGAR 0.1 deg points -> emitter country + CF-grid cell z
#   WHY : the CF matrix lives on the 91x144 grid, so every EDGAR point is binned to its cell
#         z. COUNTRY is looked up FIRST, at native 0.1 deg, so a 2 deg cell straddling a
#         border keeps each country's emissions separate ( (z, country) pairs ).
#   HOW : z = a*NLON + b flattens (row, col) to one integer - same trick as fid/cid in the
#         agricultural scripts (but row 0 = SOUTH pole here, see header).
#   CHUNKS: the CSV is ~3.2 GB / ~80M rows; 5M-row chunks + a groupby per chunk keep memory
#         flat, and the final groupby re-sums pairs split across chunk boundaries.
parts = []
def _edgar_chunks(path, n=5_000_000):
    # stream the emission database: Parquet (pyarrow batches) or the legacy CSV - same chunks either way
    if path.lower().endswith(".parquet"):
        import pyarrow.parquet as _pq
        for _b in _pq.ParquetFile(path).iter_batches(batch_size=n, columns=["Year", "lat", "lon", "IPCC", "emission"]):
            yield _b.to_pandas()
    else:
        for _c in pd.read_csv(path, usecols=["Year", "lat", "lon", "IPCC", "emission"], chunksize=n):
            yield _c
for df in _edgar_chunks(EDGAR):
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

# %% DB1) EDGAR emissions x country -- SAVED (one row per year x IPCC sector x air-cell x country).
#   Cell_ID is 1-based on the 91x144 (~2 deg) air grid, same convention as 0_gridcells_LME_mapped /
#   the per-cell outputs. The country tag was resolved at EDGAR's native 0.1 deg BEFORE binning, so
#   one air cell can (correctly) appear with several emission countries.
_z0 = E["z"].values.astype(int)
db1 = E.rename(columns={"z": "Cell_ID", "sector": "IPCC_sector", "country": "emission_country", "emis_kg": "NH3_emission_kg"}).copy()
db1["Cell_ID"] = db1["Cell_ID"] + 1
db1.insert(2, "lat", (_z0 // NLON + 0.5) * 180.0 / NLAT - 90.0)
db1.insert(3, "lon", (_z0 %  NLON + 0.5) * 360.0 / NLON - 180.0)
db1 = db1[["year", "Cell_ID", "lat", "lon", "emission_country", "IPCC_sector", "NH3_emission_kg"]]
db1.to_csv(os.path.join(OUT_DB, "NH3_DB1_emissions_cell_country_sector.csv"), index=False)
print("DB1 -> NH3_DB1_emissions_cell_country_sector.csv (%d rows, %.4e kg NH3)" % (len(db1), db1["NH3_emission_kg"].sum()))

# %% 3) receptor -> LME weights M, then ONE streamed pass over the CF matrix
#   M   : a ~2 deg receptor cell can straddle several LME sub-segments, so its deposition is
#         split by intersected area: w = AreaSqKm / sum(AreaSqKm per Cell_ID). M is
#         [13,104 x n_LME]; rows of zeros = inland / unmapped cells touching no LME.
#   CFL : row z of CF = kg O2 in EACH receptor cell per kg emitted in z; CFL = CF @ M turns
#         that into kg O2 in EACH LME per kg emitted in z. Collapsing receptors early
#         (13,104 -> 305 columns) is what lets everything downstream fit in memory.
#   STREAM: the matrix CSV is ~2.5 GB, so it is read once in 2000-row chunks; each chunk
#         also feeds rowsum (ALL receptors incl. inland - the gap check), colsum (per-
#         receptor CF summed over sources) and the per-year receptor impact maps.
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

# %% DB2) emitting cell x COUNTRY x IPCC SECTOR -> LME database, one Parquet per year.
#   Fully self-contained: each emitting air cell, per emitter country and sector, against
#   every LME it impacts, with the collapsed CF (kg O2 per kg NH3 into that LME) and the
#   eutrophication. No DB1 join needed any more (DB1 stays as the emissions-only reference).
#   SIZE NOTE: sector detail fans each cell over ~300 LMEs (~10x a sector-summed table) and
#   border cells carry 2+ countries (~1.5x more rows again). Written as PARQUET with
#   dictionary-encoded country/sector/LME strings, so bytes per row stay small.
#   Receptor stays at LME level ON PURPOSE (raw source->receptor matrix is ~85% dense,
#   13,104 x 13,104 -> a cell->cell table would be ~1e9 rows). Only LME-mapped (coastal)
#   receptors included, consistent with 'main'; the inland share is in the gap printout.
_zz2 = np.arange(N)
_lat2 = (_zz2 // NLON + 0.5) * 180.0 / NLAT - 90.0
_lon2 = (_zz2 %  NLON + 0.5) * 360.0 / NLON - 180.0
try:
    import pyarrow as _pa, pyarrow.parquet as _pq2
    _HAVE_PA = True
except ImportError:
    _HAVE_PA = False
    print("DB2: pyarrow missing -> sector- and country-SUMMED csv fallback (conda install pyarrow)")
for _Y in years_sorted:
    if not _HAVE_PA:
        _ev = evec_year[_Y]; _src = np.nonzero(_ev > 0)[0]
        _imp = _ev[_src, None] * CFL[_src]; _si, _li = np.nonzero(_imp > 0)
        _fb = pd.DataFrame({"year": _Y, "Cell_ID": _src[_si] + 1, "lat": _lat2[_src[_si]], "lon": _lon2[_src[_si]],
                            "LME_nb_f_1": labels[_li], "NH3_emission_kg": _ev[_src[_si]],
                            "CF_to_LME_kgO2_per_kg": CFL[_src[_si], _li], "eutrophication_kgO2": _imp[_si, _li]})
        _fb.to_csv(os.path.join(OUT_DB, "NH3_DB2_cell_to_LME_%d.csv" % _Y), index=False)
        continue
    _w = None; _rows = 0; _tot = 0.0
    _Ey = E[E["year"] == _Y]
    for _sec in sorted(_Ey["sector"].unique()):
        _g = _Ey[_Ey["sector"] == _sec]                 # unique (z, country) rows for this sector
        _zr  = _g["z"].values.astype(int)
        _emi = _g["emis_kg"].values
        _cty = _g["country"].values
        _imp = _emi[:, None] * CFL[_zr]                  # (rows, n_LME) kg O2 - row keeps its country
        _si, _li = np.nonzero(_imp > 0)
        if not len(_si):
            continue
        _d = pd.DataFrame({"year": np.int32(_Y), "Cell_ID": _zr[_si] + 1,
                           "lat": _lat2[_zr[_si]], "lon": _lon2[_zr[_si]],
                           "emission_country": _cty[_si], "IPCC_sector": _sec,
                           "LME_nb_f_1": labels[_li],
                           "NH3_emission_kg": _emi[_si],
                           "CF_to_LME_kgO2_per_kg": CFL[_zr[_si], _li],
                           "eutrophication_kgO2": _imp[_si, _li]})
        _t = _pa.Table.from_pandas(_d, preserve_index=False)
        if _w is None:
            _p2 = os.path.join(OUT_DB, "NH3_DB2_cell_country_sector_to_LME_%d.parquet" % _Y)
            try:
                _w = _pq2.ParquetWriter(_p2, _t.schema, compression="zstd")
            except Exception:
                _w = _pq2.ParquetWriter(_p2, _t.schema, compression="snappy")
        _w.write_table(_t)
        _rows += len(_d); _tot += _d["eutrophication_kgO2"].sum()
    if _w is not None:
        _w.close()
    print("DB2 %d -> NH3_DB2_cell_country_sector_to_LME_%d.parquet (%d rows, %.4e kg O2)" % (_Y, _Y, _rows, _tot))

# %% 4) eutrophication per (year, IPCC sector, emitter country) x LME
#   contrib : row g of E emits emis_kg in cell z -> emis * CFL[z, :] = its kg O2 per LME.
#   GROUPING: (year, sector, country) is packed into ONE integer (gcomb - the flatten trick
#         again) and np.add.at sums the LME columns per group: a pivot table without ever
#         building the full frame.
#   main  : long table year x sector x emitter x LME, with emission_kg and the EFFECTIVE
#         CF = impact / emission (a RESULT ratio; the raw CF stays in the matrix).
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

# %% 5a) inland (unmapped) gap : how much deposition never reaches an LME table
#   rowsum counts ALL receptor cells; 'main' only the LME-mapped (coastal) ones. The
#   difference = deposition on inland/unmapped cells - printed so the LME tables' coverage
#   is explicit instead of silent.
allimp = E["emis_kg"].values * rowsum[E["z"].values]
tot_all = allimp.sum(); tot_map = main["impact_kgO2"].sum()
print("mapped (coastal) impact : %.4e kg O2 (%.1f%% of all-receptor impact)" % (tot_map, 100*tot_map/tot_all))
print("inland (unmapped) gap   : %.4e kg O2 (%.1f%%)" % (tot_all-tot_map, 100*(tot_all-tot_map)/tot_all))
Eg = pd.DataFrame({"year": E["year"].values, "all": allimp}).groupby("year")["all"].sum()
mby = main.groupby("year")["impact_kgO2"].sum()
for _y in Eg.index:
    print("   year %d: mapped %.1f%%  inland %.1f%%" % (_y, 100*mby.get(_y,0)/Eg[_y], 100*(Eg[_y]-mby.get(_y,0))/Eg[_y]))

# %% 5b) per-receptor-cell impact map, one file per year (mirrors the agricultural per-cell files)
#   impact_Y(j) = sum over sources z of emis_Y(z) * CF(z, j)  ->  shows WHERE deposition
#   lands, summed over ALL sources (who caused it lives in DB2 / main). Each receptor cell
#   is tagged with its DOMINANT LME (largest intersected area; 'mapped' = touches any LME).
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
    cdf.to_csv(os.path.join(OUT_CELLS, "NH3_impact_per_cell_%d.csv" % Y), index=False)
    _tot = cdf["impact_kgO2"].sum(); _mp = cdf.loc[cdf["mapped"], "impact_kgO2"].sum()
    print("per-cell %d: %d cells, total %.4e kg O2 (mapped coastal %.1f%%)" % (Y, len(cdf), _tot, 100*_mp/_tot if _tot else 0))
print("per-cell impact maps -> NH3_impact_per_cell_<year>.csv")

# %% 5c) aggregate CF layers (aggregates of the matrix - NOT intrinsic effect factors)
#   CF_by_LME: column sums of CFL = kg O2 an LME receives per kg emitted, summed over ALL
#   source cells. CF_receptor_map: the same per receptor cell (colsum). Both depend on the
#   source grid, so label them as AGGREGATE CFs in the SI.
CF_LME = CFL.sum(axis=0)   # kg O2 in each LME per kg emitted, summed over all source cells
pd.DataFrame({"LME_nb_f_1": labels, "CF_sum_over_sources": CF_LME,
              "CF_mean_per_source": CF_LME / float(N)}).to_csv(os.path.join(OUT_CF, "NH3_CF_by_LME.csv"), index=False)
_cfmap = pd.DataFrame({"Cell_ID": zz + 1, "lat": LAT, "lon": LON, "LME_nb_f_1": lme_of_cell,
                       "mapped": mapped_cell, "CF_kgO2_per_kg": colsum})
_cfmap = _cfmap[_cfmap["CF_kgO2_per_kg"] > 0]
_cfmap.to_csv(os.path.join(OUT_CF, "NH3_CF_receptor_map.csv"), index=False)
print("CF summaries -> NH3_CF_by_LME.csv (per LME), NH3_CF_receptor_map.csv (per cell)")

# %% A5e) LME -> RECEPTOR-country split (whose EEZ makes up each LME)
#   Validated LME_country_match.csv (0_shape_files/5_LME_Country_match). Air LME labels suffix
#   single-segment LMEs as 'X_0' while the shp/match use bare 'X', so strip a trailing '_0' before
#   joining. Disputed LMEs (portions sum >1) are renormalised to 1; unclaimed (sum<1) -> ABNJ.
_MATCH = os.path.join(os.path.dirname(NH3_DIR), "0_shape_files", "5_LME_Country_match", "LME_country_match.csv")
lme_ctry = pd.read_csv(_MATCH).rename(columns={"LME_subsegment": "LME_join", "Country": "receptor_country", "LME_area_portion": "area_portion"})
lme_psum = lme_ctry.groupby("LME_join", as_index=False)["area_portion"].sum().rename(columns={"area_portion": "portion_sum"})
_mn = main.copy()
_mn["LME_join"] = _mn["LME_nb_f_1"].astype(str).str.replace(r"_0$", "", regex=True)
_rec = _mn.merge(lme_ctry, on="LME_join", how="inner").merge(lme_psum, on="LME_join", how="left")
_rec["impact_kgO2"] = _rec["impact_kgO2"] * _rec["area_portion"] / _rec["portion_sum"].clip(lower=1.0)
_res = _mn.merge(lme_psum, on="LME_join", how="left")
_res["portion_sum"] = _res["portion_sum"].fillna(0.0)
_res["receptor_country"] = "High seas (ABNJ)"
_res["impact_kgO2"] = _res["impact_kgO2"] * (1.0 - _res["portion_sum"]).clip(lower=0.0)
_cc = ["year", "IPCC_sector", "emission_country", "LME_nb_f_1", "receptor_country", "impact_kgO2"]
recept = pd.concat([_rec[_cc], _res[_cc]], ignore_index=True)
recept = recept[recept["impact_kgO2"] > 0]
recept.to_csv(os.path.join(OUT_RECEPT, "NH3_impact_emitter_LME_receptor.csv"), index=False)
by_receptor = recept.groupby(["year", "receptor_country"], as_index=False)["impact_kgO2"].sum().sort_values(["year", "impact_kgO2"], ascending=[True, False])
by_receptor.to_csv(os.path.join(OUT_RECEPT, "NH3_impact_by_receptor_country.csv"), index=False)
print("A5e receptor allocation: %d rows | total %.4e kg O2 | ABNJ %.4e (%.1f%%)" % (len(recept), recept["impact_kgO2"].sum(), _res["impact_kgO2"].sum(), 100*_res["impact_kgO2"].sum()/max(recept["impact_kgO2"].sum(),1e-30)))
