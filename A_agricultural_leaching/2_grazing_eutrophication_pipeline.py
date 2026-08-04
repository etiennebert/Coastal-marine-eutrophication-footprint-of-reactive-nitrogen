# grazing_eutrophication_pipeline.py
# ---------------------------------------------------------------------------
# Grazing (cattle) nitrogen leaching -> marine eutrophication, per 5 arcmin cell, 2015-2022.
#
# Per cell:
#   IMAGE pasture NO3 (0.5 deg, Tg N)  --split equally over the n_valid CF cells in the box-->
#   grazing_leaching (Tg N)  --x 1e9-->  kg N  --x CF (Cosme & Hauschild, per kg N)-->  eutrophication
#
# Each cell is tagged with BasinID, LME subsegment (LME_nb_f_1) and Country. Those tags depend
# only on the (static) CF grid, so they are built ONCE in PART A; only the leaching value
# changes per year (PART B).
#
# IMAGE has 5-yearly steps: 2015 and 2020 are exact; the other years are linearly interpolated
# between the bracketing steps (2016-2019 from 2015 & 2020; 2021-2022 from 2020 & 2025).
#
# Env (conda-forge): xarray netCDF4 h5netcdf geopandas pandas numpy
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
CTRY_SHP   = os.path.join(SHAPES, "1_World_Countries", "Countries_EEZ_extended.shp")
OUTDIR     = os.path.join(HERE, "6. outputs_grazing")
os.makedirs(OUTDIR, exist_ok=True)

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

# A2) BasinID for each cell (point in basin polygon)
pts = gpd.GeoDataFrame(cf, geometry=gpd.points_from_xy(cf["longitude"], cf["latitude"]), crs=4326)
basins = gpd.read_file(BASIN_SHP)[["BasinID", "geometry"]]
pts = gpd.sjoin(pts, basins, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")
pts["BasinID"] = pts["BasinID"].astype("Int64")

# A3) BasinID -> LME subsegment: nearest LME polygon to each river mouth (carries LME_nb_f_1)
mouths = pd.read_csv(MOUTH_CSV).rename(columns={"ID": "BasinID"})
mouths = gpd.GeoDataFrame(mouths, geometry=gpd.points_from_xy(mouths["Longitude"], mouths["Latitude"]), crs=4326)
lme = gpd.read_file(LME_SHP)[["LME_nb_f_1", "LME_NAME", "geometry"]]
xwalk = (gpd.sjoin_nearest(mouths, lme, how="left", distance_col="dist_deg")
            .drop_duplicates(subset="BasinID")[["BasinID", "LME_nb_f_1", "LME_NAME", "dist_deg"]])
xwalk["BasinID"] = xwalk["BasinID"].astype("Int64")
pts = pts.merge(xwalk, on="BasinID", how="left")

# A4) Country for each cell (land + EEZ so coastal cells are covered; fill rare misses with nearest)
countries = gpd.read_file(CTRY_SHP)[["Country", "geometry"]]
pts = gpd.sjoin(pts, countries, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")
miss = pts["Country"].isna()
if miss.any():
    nn = (gpd.sjoin_nearest(pts.loc[miss, ["fid", "geometry"]], countries, how="left")
             .drop_duplicates(subset="fid").set_index("fid")["Country"])
    pts.loc[miss, "Country"] = pts.loc[miss, "fid"].map(nn)

# static attribute table: one row per CF cell
cells = pd.DataFrame(pts.drop(columns="geometry"))[
    ["fid", "longitude", "latitude", "CF", "cid", "n_valid",
     "BasinID", "LME_nb_f_1", "LME_NAME", "dist_deg", "Country"]]
cells.to_csv(os.path.join(OUTDIR, "cell_attributes_static.csv"), index=False)
print("PART A done -- static cells:", len(cells))

# ===========================================================================
# PART B  -  yearly grazing leaching x CF  (loop 2015..2022)
# ===========================================================================

ds = xr.open_dataset(PASTURE_NC)                 # add engine="h5netcdf" if the default backend fails
yr2i  = {int(y): i for i, y in enumerate(ds["time"].dt.year.values)}   # year -> time index
nodes = sorted(yr2i)                                                   # IMAGE 5-yr steps

# paper Eq. S9 input: agricultural N surplus, deposition EXCLUDED
# (excluding deposition avoids double-counting with your NOx/NH3 atmospheric streams)
NSURP = (ds["NutrientSurplus"] - ds["AtmosphericDeposition"]).clip(min=0)

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
    yr_cells["eutrophication"]       = yr_cells["grazing_leaching_MtN"] * KG_PER_MT * yr_cells["CF"]

    # B3) keep cells that actually received pasture leaching; save
    out = yr_cells.dropna(subset=["grazing_leaching_MtN"]).drop(columns="L_pasture")
    out.to_csv(os.path.join(OUTDIR, "grazing_eutrophication_cells_%d.csv" % Y), index=False)
    print("%d : cells=%7d | leaching placed (Tg N)=%6.3f | eutrophication=%.4e"
          % (Y, len(out), out["grazing_leaching_MtN"].sum(), out["eutrophication"].sum()))

ds.close()
print("PART B done -- per-year files in", OUTDIR)
