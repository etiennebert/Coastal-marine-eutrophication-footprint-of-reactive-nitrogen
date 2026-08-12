# -*- coding: utf-8 -*-
"""
2_make_CF_csv_from_tif.py   --   STEP 2 of 4
Build the eutrophication characterization-factor table the pipeline joins on.
  reads   1_data_inputs/CF_arable_final.tif   (5 arcmin marine-eutrophication CF for waterborne N; Vea et al. 2022)
  writes  1_data_inputs/CF_arable.csv         (columns: id, longitude, latitude, CF)
Only cells with CF > 0 are kept (open ocean / non-contributing land are zero and dropped).
id = row*4320 + column is the same 5 arcmin cell index the pipeline uses.
Run from the project root:   python 2_scripts/2_make_CF_csv_from_tif.py
Requires: numpy, pandas, rasterio.
"""
import os
import numpy as np
import pandas as pd
import rasterio

try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))   # this script LIVES IN "3. CFs"
except NameError:
    pass   # cell-by-cell in Spyder: set the working dir to "3. CFs" first
TIF  = "CF_arable_final.tif"    # in THIS folder (3. CFs)
OUT  = "CF_arable.csv"          # written next to the tif
NCOL = 4320   # 5 arcmin grid: 4320 lon x 2160 lat

# ---- STEP 1: read the raster ----------------------------------------------------
print("STEP 1  read raster:", TIF)
with rasterio.open(TIF) as r:
    cf_grid = r.read(1).astype(np.float64)            # shape (2160 rows = lat, 4320 cols = lon)
print("   grid:", cf_grid.shape, "| CF min/max:", float(np.nanmin(cf_grid)), float(np.nanmax(cf_grid)))

# ---- STEP 2: keep positive-CF cells and give each a coordinate ------------------
print("STEP 2  keep positive-CF cells")
row_i, col_i = np.where(cf_grid > 0)                  # ocean / zero cells dropped
cf  = cf_grid[row_i, col_i]
ids = row_i.astype(np.int64) * NCOL + col_i.astype(np.int64)
lon = np.round(-180.0 + (col_i + 0.5) / 12.0, 6)      # 5 arcmin cell centres
lat = np.round( 90.0 - (row_i + 0.5) / 12.0, 6)
out = pd.DataFrame({"id": ids, "longitude": lon, "latitude": lat, "CF": cf})
print("   kept", len(out), "cells of", cf_grid.size)

# ---- STEP 3: self-check the index against the grid ------------------------------
print("STEP 3  check id = row*4320+col matches the coordinates")
fcol = np.floor((lon + 180.0) * 12).astype(np.int64)
frow = np.floor((90.0 - lat) * 12).astype(np.int64)
mism = int((frow * NCOL + fcol != ids).sum())
print("   index mismatches:", mism, "(must be 0)")

# ---- STEP 4: save ---------------------------------------------------------------
print("STEP 4  write", OUT)
out.to_csv(OUT, index=False)
print("   done:", len(out), "rows")
