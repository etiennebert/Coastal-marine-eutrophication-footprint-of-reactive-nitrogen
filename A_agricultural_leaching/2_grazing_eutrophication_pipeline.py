# grazing_eutrophication_pipeline.py
# ---------------------------------------------------------------------------
# Grazing (cattle) nitrogen leaching -> marine eutrophication, per 5 arcmin cell, 2015-2022.
#
# Per cell:
#   IMAGE pasture NO3 (0.5 deg, Tg N)  --split equally over the n_valid CF cells in the box-->
#   grazing_leaching (Tg N)  --x 1e9-->  kg N  --x CF (Cosme & Hauschild, per kg N)-->  eutrophication
#   N_reaching = eutrophication / CF_marine(LME_nb_f_1)  -> kg N ENTERING the receiving sub-segment
#   (optional input "3. CFs/CF_marine_LME.csv" [LME_nb_f_1, CF_marine]; absent -> N_reaching = NaN)
#
# Each cell is tagged with BasinID, LME subsegment (LME_nb_f_1) and Country. Those tags depend
# only on the (static) CF grid, so they are built ONCE in PART A; only the leaching value
# changes per year (PART B).
#
# IMAGE has 5-yearly steps: 2015 and 2020 are exact; the other years are linearly interpolated
# between the bracketing steps (2016-2019 from 2015 & 2020; 2021-2022 from 2020 & 2025).
#
# Env (conda-forge): xarray netCDF4 h5netcdf geopandas pandas numpy
#
# OUTPUTS (per year, in "6. outputs_grazing")
#   DB1  grazing_eutrophication_<year>.csv             one row per cell; Country_producer; stops at
#                                                       LME_nb_f_1  (NO receptor split).
#   DB2  grazing_eutrophication_LMEcountry_<year>.csv  DB1 rows expanded to Country_LME, eutrophication
#                                                       split by each country's EEZ share of the LME
#                                                       (an ASSUMPTION: impact placed uniformly in LME).
# ---------------------------------------------------------------------------

import os
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd

# ---------- paths: Supporting_Information layout (this .py sits in A_agricultural_leaching/) ----------
# Portable: found relative to THIS file, so the whole tree can be moved/renamed freely.
try:
    HERE = os.path.dirname(os.path.abspath(__file__))            # ...\A_agricultural_leaching
except NameError:                      # running cell-by-cell in Spyder
    HERE = os.getcwd()
SHAPES = os.path.join(os.path.dirname(HERE), "0_shape_files")    # ...\Supporting_Information\0_shape_files

PASTURE_NC = os.path.join(HERE, "1. Input_IMAGE_GNM", "Output-IMAGE_GNM-SSP2_oct2020-Nitrogen_PastureBudget-v2.nc")
CF_CSV     = os.path.join(HERE, "3. CFs", "CF_arable.csv")            # same data as CF_arable_final.tif
BASIN_SHP  = os.path.join(SHAPES, "3_BasinID_shape_PCR2", "BasinID_PCR2.shp")
MOUTH_CSV  = os.path.join(HERE, "MouthID_PCR2.csv")
LME_SHP    = os.path.join(SHAPES, "2_LME shape files", "cLME_ss_full.shp")
CFM_CSV    = os.path.join(HERE, "3. CFs", "CF_marine_LME.csv")        # marine-only CF per sub-segment (optional)
CTRY_SHP   = os.path.join(SHAPES, "1_World_Countries", "World_Countries.shp")
OUTDIR     = os.path.join(HERE, "6. outputs_grazing")
os.makedirs(OUTDIR, exist_ok=True)
CRS_M = 6933   # metric CRS (World Cylindrical Equal Area) for every nearest-polygon join; degrees give a wrong "nearest"

YEARS     = range(2015, 2023)          # 2015..2022
KG_PER_MT = 1e9                        # IMAGE 'MtN' = Mt N = 1e9 kg N ; CF is per kg N

# ===========================================================================
# PART A  -  static cell attributes (built ONCE; identical for every year)
#            The two spatial joins run on the full CF grid, so PART A takes a
#            few minutes. It only has to run once.
# ===========================================================================

# A1) CF grid (5 arcmin), valid land cells only; fine id, parent 0.5 deg box id, cells per box
cf = pd.read_csv(CF_CSV)[["longitude", "latitude", "CF"]]
cf = cf.dropna(subset=["CF"])
cf = cf[cf["CF"] != 0]
cf["fid"] = (np.floor((90 - cf["latitude"]) * 12).astype(int) * 4320
             + np.floor((cf["longitude"] + 180) * 12).astype(int))
cf["cid"] = (np.floor((90 - cf["latitude"]) / 0.5).astype(int) * 720
             + np.floor((cf["longitude"] + 180) / 0.5).astype(int))
cf["n_valid"] = cf.groupby("cid")["CF"].transform("size")          # valid fine cells per 0.5 deg box

# A2) GEO-JOIN 1 of 3 : each 5 arcmin land cell  ->  the river BASIN it drains to
#   WHY : leaching leaves the land through a river basin, which empties at one river mouth; we need
#         that BasinID so A3 can route the load to the sea.
#   HOW : each CF cell becomes a POINT (lon/lat, EPSG:4326); predicate="within" asks which basin
#         POLYGON contains it - a point-in-polygon test, exact in lon/lat, no projection needed.
#   NOTE: how="left" keeps unmatched cells; a border point can match twice, so drop_duplicates(fid)
#         keeps one basin per cell.
pts = gpd.GeoDataFrame(cf, geometry=gpd.points_from_xy(cf["longitude"], cf["latitude"]), crs=4326)
basins = gpd.read_file(BASIN_SHP)[["BasinID", "geometry"]]          # PCR-GLOBWB river basins
pts = gpd.sjoin(pts, basins, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")                            # one basin per cell
pts["BasinID"] = pts["BasinID"].astype("Int64")

# A3) GEO-JOIN 2 of 3 : each basin  ->  the LME sub-segment its river MOUTH falls in / nearest
#   WHY : the marine CF and the receiving sea are per LME sub-segment; a basin discharges at one
#         mouth (MouthID_PCR2.csv = one lon/lat per BasinID), which decides the LME it reaches.
#   HOW : sjoin_NEAREST matches each mouth to the closest LME polygon (nearest, not within - a mouth
#         just offshore is inside no LME).
#   CRS : "nearest" is a DISTANCE, so both layers are reprojected to a metric equal-area CRS (CRS_M,
#         metres); raw degrees give a wrong nearest near the poles. dist_m is kept as QA (0 = inside).
#   THEN: one row per basin, merged onto cells by BasinID  (cell -> basin -> LME).
mouths = pd.read_csv(MOUTH_CSV).rename(columns={"ID": "BasinID"})   # one river-mouth point per basin
mouths = gpd.GeoDataFrame(mouths, geometry=gpd.points_from_xy(mouths["Longitude"], mouths["Latitude"]), crs=4326)
lme = gpd.read_file(LME_SHP)[["LME_nb_f_1", "LME_NAME", "geometry"]]
xwalk = (gpd.sjoin_nearest(mouths.to_crs(CRS_M), lme.to_crs(CRS_M), how="left", distance_col="dist_m")
            .drop_duplicates(subset="BasinID")[["BasinID", "LME_nb_f_1", "LME_NAME", "dist_m"]])
xwalk["BasinID"] = xwalk["BasinID"].astype("Int64")
pts = pts.merge(xwalk, on="BasinID", how="left")                   # cell -> basin -> LME

#   PLUS: marine-only CF of the receiving sub-segment (kg O2 per kg N ENTERING the water) -
#   the divisor that backs the delivered N out of the impact. Tolerant label key.
_k = lambda s: s.astype(str).str.replace(r"\.0$", "", regex=True).str.replace(r"_0$", "", regex=True)
if os.path.exists(CFM_CSV):
    cfm = pd.read_csv(CFM_CSV)[["LME_nb_f_1", "CF_marine"]]
    cfm["_key"] = _k(cfm["LME_nb_f_1"])
    pts["_key"] = _k(pts["LME_nb_f_1"])
    pts = pts.merge(cfm[["_key", "CF_marine"]], on="_key", how="left").drop(columns="_key")
    print("A3  CF_marine merged:", int(pts["CF_marine"].notna().sum()), "of", len(pts), "cells")
else:
    pts["CF_marine"] = np.nan
    print("A3  NOTE: '3. CFs/CF_marine_LME.csv' not found -> N_reaching_MtN will be NaN")

# A4) GEO-JOIN 3 of 3 : each cell  ->  the PRODUCER country (where the pasture N is applied)
#   WHY : the country credited with PRODUCING the leaching (renamed Country_producer in PART B) -
#         the production side, NOT where the impact lands (that is Country_LME, from LME coverage).
#   HOW : (1) WITHIN point-in-polygon against World_Countries land polygons (COUNTRY -> Country);
#         (2) NEAREST-fill for the few coastal cells outside every land polygon (in metric CRS_M).
#         (World_Countries is land-only; maritime-zone attribution would use the eez_v11 layer.)
countries = gpd.read_file(CTRY_SHP).rename(columns={"COUNTRY": "Country"})[["Country", "geometry"]]
pts = gpd.sjoin(pts, countries, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")                            # one country per cell
miss = pts["Country"].isna()                                       # cells outside every land polygon
if miss.any():
    nn = (gpd.sjoin_nearest(pts.loc[miss, ["fid", "geometry"]].to_crs(CRS_M), countries.to_crs(CRS_M), how="left")
             .drop_duplicates(subset="fid").set_index("fid")["Country"])
    pts.loc[miss, "Country"] = pts.loc[miss, "fid"].map(nn)        # fill only the misses

# static attribute table: one row per CF cell
cells = pd.DataFrame(pts.drop(columns="geometry"))[
    ["fid", "longitude", "latitude", "CF", "CF_marine", "cid", "n_valid",
     "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m", "Country"]]
cells.to_csv(os.path.join(OUTDIR, "cell_attributes_static.csv"), index=False)
print("PART A done -- static cells:", len(cells))
fex = (cells["CF"] / cells["CF_marine"]).dropna()   # export fraction: share of released N reaching the sea; must be <= 1
if len(fex):
    print("PART A export fraction CF/CF_marine: median %.3f | max %.3f%s"
          % (fex.median(), fex.max(), "   << >1: CF_marine WRONG VINTAGE/LEVEL" if fex.max() > 1.001 else ""))

# ===========================================================================
# PART B  -  yearly grazing leaching x CF  (loop 2015..2022)
# ===========================================================================

ds = xr.open_dataset(PASTURE_NC)                 # add engine="h5netcdf" if the default backend fails
yr2i  = {int(y): i for i, y in enumerate(ds["time"].dt.year.values)}   # year -> time index
nodes = sorted(yr2i)                                                   # IMAGE 5-yr steps

# paper Eq. S9 input: agricultural N surplus, deposition EXCLUDED
# (excluding deposition avoids double-counting with your NOx/NH3 atmospheric streams)
NSURP = (ds["NutrientSurplus"] - ds["AtmosphericDeposition"]).clip(min=0)

# %% A5e SETUP) LME -> receptor-country crosswalk (validated), used in PART B's per-year loop.
#   LME_country_match.csv: per LME sub-segment, each country's EEZ area fraction (LME_area_portion)
#   from an EEZ(v11) x LME overlay - independently reproduced in Python (median fraction agreement
#   0.001), in World_Countries naming so it joins to the emission-side 'Country' tag. Disputed LMEs
#   whose portions sum >1 (overlapping EEZ claims) are renormalised to 1 so totals stay conserved;
#   the unclaimed remainder (sum<1) is booked to 'High seas (ABNJ)'.
LME_CTRY_MATCH = os.path.join(SHAPES, "5_LME_Country_match", "LME_country_match.csv")
lme_ctry = pd.read_csv(LME_CTRY_MATCH).rename(
    columns={"LME_subsegment": "LME_nb_f_1", "Country": "receptor_country", "LME_area_portion": "area_portion"})
lme_psum = lme_ctry.groupby("LME_nb_f_1", as_index=False)["area_portion"].sum().rename(columns={"area_portion": "portion_sum"})
print("A5e  LME->receptor match:", lme_ctry["LME_nb_f_1"].nunique(), "sub-segments,", lme_ctry["receptor_country"].nunique(), "countries")

for Y in YEARS:
    # B1) IMAGE pasture N surplus for year Y (Tg N per 0.5 deg box); exact on a step, else interpolated
    y0 = max(y for y in nodes if y <= Y)
    y1 = min(y for y in nodes if y >= Y)
    if y1 == y0:
        da = NSURP.isel(time=yr2i[Y])
    else:
        w  = (Y - y0) / (y1 - y0)
        da = (1 - w) * NSURP.isel(time=yr2i[y0]) + w * NSURP.isel(time=yr2i[y1])
    pas = da.to_dataframe(name="Nsurp").reset_index()[["lon", "lat", "Nsurp"]]
    pas.columns = ["lon", "lat", "L_pasture"]
    pas = pas.dropna(subset=["L_pasture"])
    pas = pas[pas["L_pasture"] != 0]
    pas["cid"] = (np.floor((90 - pas["lat"]) / 0.5).astype(int) * 720
                  + np.floor((pas["lon"] + 180) / 0.5).astype(int))
        

    # B2) spread each box value equally over its valid CF cells, then x1e9, then x CF
    yr_cells = cells.merge(pas[["cid", "L_pasture"]], on="cid", how="left")
    yr_cells["grazing_leaching_MtN"] = yr_cells["L_pasture"] / yr_cells["n_valid"]
    yr_cells["eutrophication"]       = yr_cells["grazing_leaching_MtN"] * KG_PER_MT * yr_cells["CF"]   # result in kg O2 (marine O2 depletion) = kg N x CF[kg O2 per kg N] (Cosme & Hauschild)
    yr_cells["N_reaching_MtN"]       = yr_cells["eutrophication"] / yr_cells["CF_marine"] / KG_PER_MT   # Mt N ENTERING the sub-segment's water (NaN without CF_marine)

    # B3) keep cells that actually received pasture leaching; save
    # ---- DATABASE 1 : the honest per-cell result -- NO receptor assumption ------------------------
    #   One row per producing cell. Country_producer = where the pasture N is applied; LME_nb_f_1 =
    #   the sea the leaching reaches. DB1 stops at the LME (we do not know where inside it the impact
    #   lands). Use this table for producer-side / footprint results.
    out = yr_cells.dropna(subset=["grazing_leaching_MtN"]).drop(columns="L_pasture").rename(columns={"Country": "Country_producer"})
    out.insert(0, "year", Y)
    db1 = out[["year", "fid", "longitude", "latitude", "Country_producer", "CF", "CF_marine", "cid", "n_valid",
               "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m",
               "grazing_leaching_MtN", "N_reaching_MtN", "eutrophication"]]
    db1.to_csv(os.path.join(OUTDIR, "grazing_eutrophication_%d.csv" % Y), index=False)
    rtxt = ("%.3f" % db1["N_reaching_MtN"].sum()) if db1["N_reaching_MtN"].notna().any() else "n/a"
    print("%d : DB1 cell-rows=%7d | leaching placed (Tg N)=%6.3f | reaching sea=%s Tg N | eutrophication(kg O2)=%.4e"
          % (Y, len(db1), db1["grazing_leaching_MtN"].sum(), rtxt, db1["eutrophication"].sum()))

    # ---- DATABASE 2 : receptor attribution -- ARTIFICIAL split by EEZ coverage of the LME ---------
    #   Assumption: impact spread uniformly over the LME, so each cell's eutrophication is divided
    #   among the countries whose EEZ makes up that LME, by area share (a MODELLING CHOICE). Only the
    #   eutrophication is split (not the land-side leaching). Each DB1 row -> one row per receptor.
    #
    #   THE MERGE (the geographic attribution):
    #     db1 [key = LME_nb_f_1]  x  lme_ctry [LME_nb_f_1 -> receptor_country, area_portion]
    #     how="inner" expands a cell to one row per covering country. w = area_portion / max(1, sum)
    #     renormalises disputed LMEs (sum>1); the uncovered remainder (sum<1) becomes one
    #     'High seas (ABNJ)' row, so the per-cell eutrophication is conserved exactly.
    rc = db1.merge(lme_ctry, on="LME_nb_f_1", how="inner").merge(lme_psum, on="LME_nb_f_1", how="left")
    rc["Country_LME"] = rc["receptor_country"]
    rc["w"]           = rc["area_portion"] / rc["portion_sum"].clip(lower=1.0)   # renormalised EEZ share
    abnj = db1.merge(lme_psum, on="LME_nb_f_1", how="left")
    abnj["portion_sum"] = abnj["portion_sum"].fillna(0.0)          # LME absent from match -> 0 covered
    abnj["Country_LME"] = "High seas (ABNJ)"
    abnj["w"]           = (1.0 - abnj["portion_sum"]).clip(lower=0.0)            # uncovered remainder
    db2 = pd.concat([rc, abnj], ignore_index=True)
    db2["eutrophication"] = db2["eutrophication"] * db2["w"]       # split the marine impact only
    db2 = db2[db2["eutrophication"] > 0]
    db2 = db2[["year", "fid", "longitude", "latitude", "Country_producer", "CF", "cid", "n_valid",
               "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m", "Country_LME", "eutrophication"]]
    db2.to_csv(os.path.join(OUTDIR, "grazing_eutrophication_LMEcountry_%d.csv" % Y), index=False)
    print("       DB2 receptor-rows=%7d (producer x LME-country) | conserved=%.4e kg O2 -> grazing_eutrophication_LMEcountry_%d.csv"
          % (len(db2), db2["eutrophication"].sum(), Y))

ds.close()
print("PART B done -- per-year files in", OUTDIR)
