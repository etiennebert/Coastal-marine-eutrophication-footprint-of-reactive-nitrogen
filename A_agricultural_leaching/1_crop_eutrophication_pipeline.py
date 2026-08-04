# 1_crop_eutrophication_pipeline.py
# ---------------------------------------------------------------------------
# Cropland (crop-disaggregated) nitrogen leaching -> marine eutrophication,
# per 5 arcmin cell AND crop, 2015-2022.  Twin of 2_grazing_eutrophication_pipeline.py.
#
# HOW TO RUN
#   * Whole file:            F5 in Spyder, or  python 1_crop_eutrophication_pipeline.py
#   * Step by step (Spyder):  the code is split into  "# %%"  cells - put the cursor in a
#                             cell and press Ctrl+Enter, top to bottom. No functions and no
#                             hidden state: every line leaves a plain pandas/numpy variable
#                             (cf, pts, cells, adal, alloc, box, out) you can open in the
#                             Variable Explorer and inspect.
#   * PART A (the two spatial joins) is the slow part (a few minutes) and only has to run
#     ONCE. After it, you can re-run PART B (the yearly loop) as often as you like - it's fast.
#
# METHOD   (P = leaching potential = the weight; IMAGE fixes the magnitude, the weights split it)
#   per 0.5 deg box g:  L(cell,crop) = L_box(g) * P / sum(P over the box),
#                       P = Nsyn*LF_crop + Nman*LF_organic
#   E(cell,crop) = L(cell,crop) * 1e9 (kgN per MtN) * CF(cell)          -> marine eutrophication
#   Atmospheric deposition is REMOVED from the IMAGE surplus so this does not double-count
#   the separate airborne NH3 / NOx streams.
#
# DOWNLOAD STATUS (important)
#   Harvested_area_1961-2020.h5 may still be downloading (~2.8 GB complete). If it cannot be
#   read, the script AUTOMATICALLY falls back to the application-RATE weight (a valid draft)
#   and prints which crops fell back - it will NOT crash. Finish the download (run
#   a_download_adalibieke.py) for the final, area-weighted result.
#
# Env (conda-forge):  xarray netCDF4 h5netcdf geopandas pandas numpy h5py
# ---------------------------------------------------------------------------

# %% imports + paths  (nothing to edit - every path is relative to THIS file)
import os
import glob
import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import h5py

try:
    HERE = os.path.dirname(os.path.abspath(__file__))            # ...\A_agricultural_leaching
except NameError:                      # running cell-by-cell in Spyder, __file__ is undefined
    HERE = os.getcwd()
SHAPES = os.path.join(os.path.dirname(HERE), "0_shape_files")    # ...\Supporting_Information\0_shape_files

CROPLAND_NC = os.path.join(HERE, "1. Input_IMAGE_GNM", "Output-IMAGE_GNM-SSP2_oct2020-Nitrogen_CroplandBudget-v2.nc")
CF_CSV      = os.path.join(HERE, "3. CFs", "CF_arable.csv")
LF_CSV      = os.path.join(HERE, "4. Leaching_factors", "Wang2025_leaching_factors.csv")
ADAL_DIR    = os.path.join(HERE, "2. N_application_rate")
AREA_FILE   = os.path.join(ADAL_DIR, "Harvested_area_1961-2020.h5")
BASIN_SHP   = os.path.join(SHAPES, "3_BasinID_shape_PCR2", "BasinID_PCR2.shp")
MOUTH_CSV   = os.path.join(HERE, "MouthID_PCR2.csv")
LME_SHP     = os.path.join(SHAPES, "2_LME shape files", "cLME_ss_full.shp")
CTRY_SHP    = os.path.join(SHAPES, "1_World_Countries", "Countries_EEZ_extended.shp")
OUTDIR      = os.path.join(HERE, "5. outputs_crops")
os.makedirs(OUTDIR, exist_ok=True)

YEARS     = range(2015, 2023)          # 2015..2022 (IMAGE leaching years)
KG_PER_MT = 1e9                        # IMAGE 'MtN' = Mt N = 1e9 kg N ; CF is per kg N
ADAL_YEAR = 2020                       # reference year for the crop weights (Adalibieke covers 1961-2020)

SYNTH_FORMS    = ["AA", "AN", "AS", "CAN", "NS", "ONS", "Urea", "AP", "NK", "NPK", "ONP"]  # 11 synthetic forms
CROP_MAP       = [("maize", "Maize"), ("corn", "Maize"), ("wheat", "Wheat"),
                  ("rice", "Rice"), ("paddy", "Rice"), ("veg", "Vegetable")]
OTHER_LF_CLASS = "Other upland crops"

print("HERE   =", HERE)
print("OUTDIR =", OUTDIR)

# %% A1) CF grid (5 arcmin) -> valid land cells, with fine id (fid) + parent 0.5 deg box id (cid)
cf = pd.read_csv(CF_CSV)[["longitude", "latitude", "CF"]]
cf = cf.dropna(subset=["CF"])
cf = cf[cf["CF"] != 0]                                    # drop ocean / zero-CF cells
cf["fid"] = (np.floor((90 - cf["latitude"]) * 12).astype(int) * 4320
             + np.floor((cf["longitude"] + 180) * 12).astype(int))
cf["cid"] = (np.floor((90 - cf["latitude"]) / 0.5).astype(int) * 720
             + np.floor((cf["longitude"] + 180) / 0.5).astype(int))
print("A1  CF land cells:", len(cf))

# %% A2) tag each cell with its BasinID (point-in-polygon)      [SLOW: spatial join]
pts = gpd.GeoDataFrame(cf, geometry=gpd.points_from_xy(cf["longitude"], cf["latitude"]), crs=4326)
basins = gpd.read_file(BASIN_SHP)[["BasinID", "geometry"]]
pts = gpd.sjoin(pts, basins, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")
pts["BasinID"] = pts["BasinID"].astype("Int64")
print("A2  cells tagged with BasinID")

# %% A3) BasinID -> LME sub-segment (nearest LME polygon to each river mouth; carries LME_nb_f_1)
mouths = pd.read_csv(MOUTH_CSV).rename(columns={"ID": "BasinID"})
mouths = gpd.GeoDataFrame(mouths, geometry=gpd.points_from_xy(mouths["Longitude"], mouths["Latitude"]), crs=4326)
lme = gpd.read_file(LME_SHP)[["LME_nb_f_1", "LME_NAME", "geometry"]]
xwalk = (gpd.sjoin_nearest(mouths, lme, how="left", distance_col="dist_deg")
            .drop_duplicates(subset="BasinID")[["BasinID", "LME_nb_f_1", "LME_NAME", "dist_deg"]])
xwalk["BasinID"] = xwalk["BasinID"].astype("Int64")
pts = pts.merge(xwalk, on="BasinID", how="left")
print("A3  BasinID -> LME crosswalk merged")

# %% A4) tag each cell with its Country (land + EEZ; nearest fill for rare misses)   [SLOW: spatial join]
countries = gpd.read_file(CTRY_SHP)[["Country", "geometry"]]
pts = gpd.sjoin(pts, countries, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")
miss = pts["Country"].isna()
if miss.any():
    nn = (gpd.sjoin_nearest(pts.loc[miss, ["fid", "geometry"]], countries, how="left")
             .drop_duplicates(subset="fid").set_index("fid")["Country"])
    pts.loc[miss, "Country"] = pts.loc[miss, "fid"].map(nn)

cells = pd.DataFrame(pts.drop(columns="geometry"))[
    ["fid", "longitude", "latitude", "CF", "cid",
     "BasinID", "LME_nb_f_1", "LME_NAME", "dist_deg", "Country"]]
cells.to_csv(os.path.join(OUTDIR, "cell_attributes_static.csv"), index=False)
print("A4  static cells:", len(cells), "-> saved cell_attributes_static.csv")

# %% A5a) leaching factors (Wang 2025): crop LFs + the organic(manure) LF
lf = pd.read_csv(LF_CSV)
crop_lf, organic_lf = {}, 13.3
for _, r in lf.iterrows():
    g, cat, val = str(r["group"]).lower(), str(r["category"]), float(r["LF_percent"])
    if g.startswith("crop"):
        crop_lf[cat] = val
    if "fertilizer" in g and cat.lower() == "organic":
        organic_lf = val
print("A5a crop LFs:", crop_lf, "| organic LF:", organic_lf)

# %% A5b) open the harvested-area file ONCE (rate x area if possible, else rate-only)
#     The file may still be downloading. We test-read one dataset to catch a truncated file;
#     if anything fails we drop to RATE-only (a valid draft). The loop in A5c is guarded too,
#     so a partial file can NEVER crash the run.
yi = ADAL_YEAR - 1961
USE_AREA, area_h5, area_keys = False, None, []
try:
    area_h5 = h5py.File(AREA_FILE, "r")
    area_keys = list(area_h5.keys())
    _probe = area_h5[area_keys[0]][yi, :, :]                 # touch data -> raises if truncated
    USE_AREA = True
    print("A5b harvested-area readable -> weight = rate x area (kg N per cell)")
except Exception as e:
    USE_AREA = False
    print("A5b harvested-area NOT usable (%s) -> DRAFT weight = application RATE only" % type(e).__name__)

# %% A5c) read each crop's N application (synthetic + manure) for year ADAL_YEAR -> table `adal`
crop_files = sorted(glob.glob(os.path.join(ADAL_DIR, "N_application_rate_*_1961-2020.h5")))
print("A5c Adalibieke crop files found:", len(crop_files))
frames, skipped, rate_only_crops = [], [], []
for f in crop_files:
    crop = os.path.basename(f).replace("N_application_rate_", "").replace("_1961-2020.h5", "")
    try:
        h = h5py.File(f, "r")
    except OSError:
        skipped.append(crop); print("   SKIP %-14s (incomplete / still downloading)" % crop); continue
    try:
        present = set(h.keys())
        nsyn = np.zeros((4320, 2160), dtype="float64")       # (lon, lat)
        for form in SYNTH_FORMS:
            for place in ("_deep", "_surface"):
                if form + place in present:
                    nsyn += np.nan_to_num(h[form + place][yi, :, :].astype("float64"))
        nman = np.zeros((4320, 2160), dtype="float64")
        for place in ("_deep", "_surface"):
            if "MA" + place in present:
                nman += np.nan_to_num(h["MA" + place][yi, :, :].astype("float64"))
    except (OSError, KeyError):
        skipped.append(crop); h.close(); print("   SKIP %-14s (partial read)" % crop); continue
    h.close()

    # optional rate -> amount: multiply by harvested area (ha). Guarded: if this crop's area
    # slice is missing/truncated, keep the rate weight instead of crashing.
    if USE_AREA:
        match = [k for k in area_keys if k.lower() == crop.lower()]
        if match:
            try:
                area = np.nan_to_num(area_h5[match[0]][yi, :, :].astype("float64"))
                nsyn, nman = nsyn * area, nman * area
            except Exception:
                rate_only_crops.append(crop)

    keep = (nsyn + nman) > 0
    ci, ri = np.where(keep)                                  # ci = lon index, ri = lat index
    lon = -180.0 + (ci + 0.5) / 12.0
    lat = 90.0 - (ri + 0.5) / 12.0
    frames.append(pd.DataFrame({"longitude": lon, "latitude": lat, "crop": crop,
                                "Nsyn": nsyn[keep], "Nman": nman[keep]}))
    print("   %-14s cells=%d" % (crop, int(keep.sum())))

if area_h5 is not None:
    area_h5.close()
if skipped:
    print("   NOTE: %d crop(s) skipped (still downloading): %s" % (len(skipped), ", ".join(skipped)))
if rate_only_crops:
    print("   NOTE: %d crop(s) used RATE-only (area read failed): %s" % (len(rate_only_crops), ", ".join(rate_only_crops)))
if not frames:
    raise SystemExit("No crop files could be read - finish the download (a_download_adalibieke.py) first.")

adal = pd.concat(frames, ignore_index=True)
print("A5c crop rows:", len(adal), "| crops used:", sorted(adal["crop"].unique()))

# %% A5d) leaching potential P per (cell, crop), and each crop's SHARE inside its 0.5 deg box
adal["fid"] = (np.floor((90 - adal["latitude"]) * 12).astype(int) * 4320
               + np.floor((adal["longitude"] + 180) * 12).astype(int))
adal = adal.drop(columns=["longitude", "latitude"]).merge(cells, on="fid", how="inner")   # onto CF mask + tags
adal["lf_class"] = OTHER_LF_CLASS
for key, cls in CROP_MAP:
    adal.loc[adal["crop"].str.lower().str.contains(key), "lf_class"] = cls
adal["LF_c"]  = adal["lf_class"].map(crop_lf).fillna(crop_lf.get(OTHER_LF_CLASS, np.nan))
adal["P"]     = adal["Nsyn"] * adal["LF_c"] + adal["Nman"] * organic_lf
adal = adal[adal["P"] > 0].copy()
adal["share"] = adal["P"] / adal.groupby("cid")["P"].transform("sum")     # crop share within each 0.5 deg box
alloc = adal[["fid", "cid", "crop", "lf_class", "share",
              "longitude", "latitude", "CF", "BasinID", "LME_nb_f_1", "LME_NAME", "dist_deg", "Country"]]
print("A5d (cell x crop) allocation rows:", len(alloc))

# %% PART B) per year: IMAGE cropland leaching -> allocate to (cell, crop) -> x CF -> save
ds = xr.open_dataset(CROPLAND_NC)                            # add engine="h5netcdf" if the default backend fails
yr2i  = {int(y): i for i, y in enumerate(ds["time"].dt.year.values)}
nodes = sorted(yr2i)                                         # IMAGE 5-yr steps (1970..2070)
# agricultural N surplus with atmospheric deposition EXCLUDED (avoids double-counting NH3/NOx)
NSURP = (ds["NutrientSurplus"] - ds["AtmosphericDeposition"]).clip(min=0)

for Y in YEARS:
    y0 = max(y for y in nodes if y <= Y)                     # bracket Y between IMAGE steps
    y1 = min(y for y in nodes if y >= Y)
    if y1 == y0:
        da = NSURP.isel(time=yr2i[Y])                        # exact step (2015, 2020)
    else:
        w  = (Y - y0) / (y1 - y0)                            # linear interpolation otherwise
        da = (1 - w) * NSURP.isel(time=yr2i[y0]) + w * NSURP.isel(time=yr2i[y1])
    box = da.to_dataframe(name="Nsurp").reset_index()[["lon", "lat", "Nsurp"]]
    box.columns = ["lon", "lat", "L_box"]
    box = box.dropna(subset=["L_box"])
    box = box[box["L_box"] != 0]
    box["cid"] = (np.floor((90 - box["lat"]) / 0.5).astype(int) * 720
                  + np.floor((box["lon"] + 180) / 0.5).astype(int))

    a = alloc.merge(box[["cid", "L_box"]], on="cid", how="left")
    a["crop_leaching_MtN"] = a["L_box"] * a["share"]         # split the box total by crop share
    a["eutrophication"]    = a["crop_leaching_MtN"] * KG_PER_MT * a["CF"]

    out = a.dropna(subset=["crop_leaching_MtN"])
    out = out[["fid", "longitude", "latitude", "crop", "lf_class", "CF", "cid",
               "BasinID", "LME_nb_f_1", "LME_NAME", "dist_deg", "Country",
               "crop_leaching_MtN", "eutrophication"]]
    out.to_csv(os.path.join(OUTDIR, "crop_eutrophication_cells_%d.csv" % Y), index=False)
    print("%d : rows=%8d | placed=%6.3f of IMAGE %6.3f Tg N (%.0f%%) | eutrophication=%.4e"
          % (Y, len(out), out["crop_leaching_MtN"].sum(), box["L_box"].sum(),
             100 * out["crop_leaching_MtN"].sum() / box["L_box"].sum(), out["eutrophication"].sum()))

ds.close()
print("DONE -- per-year crop files written to", OUTDIR)
