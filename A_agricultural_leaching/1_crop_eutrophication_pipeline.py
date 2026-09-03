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
#                             (cf, pts, cells, adal, alloc, box, out, db1, db2) you can open in the
#                             Variable Explorer and inspect.
#   * PART A (the two spatial joins) is the slow part (a few minutes) and only has to run
#     ONCE. After it, you can re-run PART B (the yearly loop) as often as you like - it's fast.
#
# METHOD   (P = leaching potential = the weight; IMAGE fixes the magnitude, the weights split it)
#   per 0.5 deg box g:  L(cell,crop) = L_box(g) * P / sum(P over the box),
#                       P = Nsyn*LF_crop + Nman*LF_organic
#   E(cell,crop) = L(cell,crop) * 1e9 (kgN per MtN) * CF(cell)          -> marine eutrophication
#   Fraction_N_marine(cell) = CF(cell) / FFmar_XF(basin)  - the fraction of released N that
#   reaches the sea (CF = export-to-sea x FF_mar x XF, so dividing by the per-BASIN marine
#   tail FFmar_XF leaves the export fraction; <= 1 by construction).
#   N_reaching(cell,crop) = L(cell,crop) * Fraction_N_marine  -> N ENTERING the receiving water.
#   Atmospheric deposition is REMOVED from the IMAGE surplus so this does not double-count
#   the separate airborne NH3 / NOx streams.
#
# OUTPUTS (per year, in "5. outputs_crops")
#   DB1  crop_eutrophication_<year>.csv             one row per (cell, crop); Country_producer;
#                                                   stops at LME_nb_f_1  (NO receptor split).
#   DB2  crop_eutrophication_LMEcountry_<year>.csv  DB1 rows expanded to Country_LME, eutrophication
#                                                   split by each country's EEZ share of the LME
#                                                   (an ASSUMPTION: impact placed uniformly in LME).
#
# OPTIONAL INPUTS (both from c_make_FFmar_XF_basin.py, in "3. CFs"):
#   FFmar_XF_basin.csv       marine tail XF/removal_final per RIVER BASIN, taken from
#                            SOS_airgrid.xls - the table CF_arable itself was built from
#                            (validated: CF/tail saturates at 1, p99 = 0.99).
#   FFmar_XF_subsegment.csv  fallback for small basins absent from the 2-deg air grid:
#                            the sub-segment's median tail, floored at the basin's max CF.
#   Files absent -> the pipeline runs unchanged, the new columns are NaN.
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
FFX_CSV     = os.path.join(HERE, "3. CFs", "FFmar_XF_basin.csv")       # marine tail per river basin (optional)
FFS_CSV     = os.path.join(HERE, "3. CFs", "FFmar_XF_subsegment.csv")  # sub-segment fallback (optional)

CTRY_SHP    = os.path.join(SHAPES, "1_World_Countries", "World_Countries.shp")
EEZ_SHP     = os.path.join(SHAPES, "4_World_EEZ_v11", "eez_v11.shp")

OUTDIR      = os.path.join(HERE, "5. outputs_crops")
os.makedirs(OUTDIR, exist_ok=True)
CRS_M = 6933   # metric CRS (World Cylindrical Equal Area) for every nearest-polygon join; degrees give a wrong "nearest"
SAVE_ADAL_SPLIT = True   # option: dump the per-(cell,crop) Adalibieke split to "2. N_application_rate" for inspection (set False to skip)

YEARS     = range(2015, 2023)          # 2015..2022 (IMAGE leaching years)
KG_PER_MT = 1e9                        # IMAGE 'MtN' = Mt N = 1e9 kg N ; CF is per kg N
ADAL_YEAR = 2020                       # reference year for the crop weights (Adalibieke covers 1961-2020)

SYNTH_FORMS    = ["AA", "AN", "AS", "CAN", "NS", "ONS", "Urea", "AP", "NK", "NPK", "ONP"]  # 11 synthetic forms
CROP_MAP       = [("maize", "Maize"), ("corn", "Maize"), ("wheat", "Wheat"),
                  ("rice", "Rice"), ("paddy", "Rice"), ("veg", "Vegetable")]
OTHER_LF_CLASS = "Other upland crops"

print("HERE   =", HERE)
print("OUTDIR =", OUTDIR)

# %% A1) CF grid (5 arcmin) -> valid land cells, with fine id (fid) + parent 0.5 deg box id (coarse id, cid)
cf = pd.read_csv(CF_CSV)[["longitude", "latitude", "CF"]]
cf = cf.dropna(subset=["CF"])
cf = cf[cf["CF"] != 0]                                    # drop ocean / zero-CF cells
cf["fid"] = (np.floor((90 - cf["latitude"]) * 12).astype(int) * 4320
             + np.floor((cf["longitude"] + 180) * 12).astype(int))
cf["cid"] = (np.floor((90 - cf["latitude"]) / 0.5).astype(int) * 720
             + np.floor((cf["longitude"] + 180) / 0.5).astype(int))
print("A1  CF land cells:", len(cf))

# %% A2) GEO-JOIN 1 of 3 : each 5 arcmin land cell  ->  the river BASIN it drains to
#   WHY : leaching leaves the land through a river basin, and every basin empties at one river
#         mouth. We need that BasinID so A3 can route the basin's load to the right sea (LME).
#   HOW : make each CF cell a POINT at its centre (lon/lat, EPSG:4326) and ask which basin POLYGON
#         contains it. predicate="within" is a point-in-polygon test - no distance, so it is exact
#         in lon/lat and needs no projection.
#   NOTE: how="left" keeps a cell even if it matches no basin; a point on a shared border can match
#         twice, so drop_duplicates(fid) keeps one basin per cell (fid = the 5 arcmin cell id).
pts = gpd.GeoDataFrame(cf, geometry=gpd.points_from_xy(cf["longitude"], cf["latitude"]), crs=4326)
basins = gpd.read_file(BASIN_SHP)[["BasinID", "geometry"]]          # PCR-GLOBWB river basins
pts = gpd.sjoin(pts, basins, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")                            # one basin per cell
pts["BasinID"] = pts["BasinID"].astype("Int64")
print("A2  cells tagged with BasinID")

# %% A3) GEO-JOIN 2 of 3 : each basin  ->  the LME sub-segment its river MOUTH falls in / nearest
#   WHY : the marine eutrophication CF and the receiving sea are defined per LME sub-segment. A
#         basin discharges at one mouth (MouthID_PCR2.csv = one lon/lat per BasinID), so the mouth
#         decides which LME the basin's nitrogen reaches.
#   HOW : sjoin_NEAREST matches each mouth point to the closest LME polygon. NEAREST (not within)
#         because a mouth just offshore is inside no LME polygon.
#   CRS : "nearest" is a DISTANCE, so both layers are reprojected to a metric equal-area CRS (CRS_M,
#         metres). In raw degrees the nearest polygon can be wrong (a degree of longitude shrinks
#         toward the poles). dist_m is kept as QA: 0 = mouth inside its LME; large = a far/inland
#         basin whose LME is only a "nearest" guess.
#   THEN: one row per basin (drop_duplicates BasinID), merged onto cells by BasinID, so every cell
#         inherits the LME of the basin it drains to  (cell -> basin -> LME).
mouths = pd.read_csv(MOUTH_CSV).rename(columns={"ID": "BasinID"})   # one river-mouth point per basin
mouths = gpd.GeoDataFrame(mouths, geometry=gpd.points_from_xy(mouths["Longitude"], mouths["Latitude"]), crs=4326)
lme = gpd.read_file(LME_SHP)[["LME_nb_f_1", "LME_NAME", "geometry"]]
xwalk = (gpd.sjoin_nearest(mouths.to_crs(CRS_M), lme.to_crs(CRS_M), how="left", distance_col="dist_m")
            .drop_duplicates(subset="BasinID")[["BasinID", "LME_nb_f_1", "LME_NAME", "dist_m"]])
xwalk["BasinID"] = xwalk["BasinID"].astype("Int64")
pts = pts.merge(xwalk, on="BasinID", how="left")                   # cell -> basin -> LME
print("A3  BasinID -> LME crosswalk merged")

#   PLUS: the marine tail XF/removal_final of each cell's BASIN (SOS_airgrid vintage - the
#   one CF_arable was built from; validated: CF/tail saturates at 1). Small basins missing
#   from the 2-deg air grid fall back to their sub-segment's median tail, floored at the
#   basin's own max CF (export fraction <= 1); residual join noise is clipped at 1, counted.
if os.path.exists(FFX_CSV):
    ffx = pd.read_csv(FFX_CSV)[["BasinID", "FFmar_XF"]]
    ffx["BasinID"] = ffx["BasinID"].astype("Int64")
    pts = pts.merge(ffx, on="BasinID", how="left")
    n_basin = int(pts["FFmar_XF"].notna().sum())
    if os.path.exists(FFS_CSV):
        ssm = pd.read_csv(FFS_CSV)
        _k = lambda x: x.astype(str).str.replace(r"\.0$", "", regex=True).str.replace(r"_0$", "", regex=True)
        tail_ss = _k(pts["LME_nb_f_1"]).map(dict(zip(_k(ssm["LME_nb_f_1"]), ssm["FFmar_XF_ss"])))
        cfmax   = pts.groupby("BasinID")["CF"].transform("max")
        miss    = pts["FFmar_XF"].isna()
        pts.loc[miss, "FFmar_XF"] = np.fmax(tail_ss[miss], cfmax[miss])
    fr = pts["CF"] / pts["FFmar_XF"]
    n_clip = int((fr > 1.0001).sum())
    pts["Fraction_N_marine"] = fr.clip(upper=1.0)
    print("A3  marine tail: %d cells per-basin, %d via sub-segment fallback, %d unmatched | %d clipped at 1"
          % (n_basin, int(pts["FFmar_XF"].notna().sum()) - n_basin,
             int(pts["FFmar_XF"].isna().sum()), n_clip))
else:
    pts["Fraction_N_marine"] = np.nan
    print("A3  NOTE: '3. CFs/FFmar_XF_basin.csv' not found (run c_make_FFmar_XF_basin.py)"
          " -> Fraction_N_marine / N_reaching_MtN will be NaN")

# %% A4) GEO-JOIN 3 of 3 : each cell  ->  the PRODUCER country (where the crop N is applied)
#   WHY : this is the country credited with PRODUCING the leaching (renamed Country_producer in
#         PART B). It is the emission/production side - NOT where the impact lands (that is
#         Country_LME, built in PART B from the LME->country coverage).
#   HOW : two steps.
#     (1) WITHIN  : point-in-polygon against World_Countries land polygons (field COUNTRY->Country).
#                   Nearly all arable cells are on land, so this resolves the vast majority exactly.
#     (2) NEAREST : a few coastal cells fall just outside every land polygon (miss = NaN). For ONLY
#                   those, sjoin_nearest assigns the closest country - again in metric CRS_M so
#                   "nearest" is a real distance. (World_Countries is land-only; to attribute coastal
#                   cells by maritime zone instead of nearest-land, use the eez_v11 layer.)
countries = gpd.read_file(CTRY_SHP).rename(columns={"COUNTRY": "Country"})[["Country", "geometry"]]
pts = gpd.sjoin(pts, countries, predicate="within", how="left").drop(columns="index_right")
pts = pts.drop_duplicates(subset="fid")                            # one country per cell
miss = pts["Country"].isna()                                       # cells outside every land polygon
if miss.any():
    nn = (gpd.sjoin_nearest(pts.loc[miss, ["fid", "geometry"]].to_crs(CRS_M), countries.to_crs(CRS_M), how="left")
             .drop_duplicates(subset="fid").set_index("fid")["Country"])
    pts.loc[miss, "Country"] = pts.loc[miss, "fid"].map(nn)        # fill only the misses

cells = pd.DataFrame(pts.drop(columns="geometry"))[
    ["fid", "longitude", "latitude", "CF", "Fraction_N_marine", "cid",
     "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m", "Country"]]
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
              "longitude", "latitude", "CF", "Fraction_N_marine", "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m", "Country"]]
print("A5d (cell x crop) allocation rows:", len(alloc))
fex = alloc["Fraction_N_marine"].dropna()           # share of released N reaching the sea; must be <= 1
if len(fex):
    print("A5d Fraction_N_marine: median %.3f | max %.3f%s"
          % (fex.median(), fex.max(), "   << >1: FFmar_XF WRONG VINTAGE" if fex.max() > 1.001 else ""))
if SAVE_ADAL_SPLIT:
    _split_cols = ["fid", "longitude", "latitude", "cid", "crop", "lf_class",
                   "Nsyn", "Nman", "LF_c", "P", "share", "CF",
                   "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m", "Country"]
    _sp = os.path.join(ADAL_DIR, "adalibieke_crop_split_check.csv")
    adal[_split_cols].to_csv(_sp, index=False)
    print("A5d saved Adalibieke split -> 2. N_application_rate/adalibieke_crop_split_check.csv (%d rows)" % len(adal))


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
    a["eutrophication"]    = a["crop_leaching_MtN"] * KG_PER_MT * a["CF"]   # result in kg O2 (marine O2 depletion) = kg N x CF[kg O2 per kg N] (Cosme & Hauschild)
    a["N_reaching_MtN"]    = a["crop_leaching_MtN"] * a["Fraction_N_marine"]    # Mt N ENTERING the receiving water (NaN without FFmar_XF)

    # ---- DATABASE 1 : the honest per-(cell, crop) result -- NO receptor assumption ----------------
    #   One row per producing cell x crop. Country_producer = where the N is applied; LME_nb_f_1 =
    #   the sea the leaching reaches. We do NOT know WHERE inside that LME the impact lands, so DB1
    #   stops at the LME. Use this table for producer-side / footprint results.
    out = a.dropna(subset=["crop_leaching_MtN"]).rename(columns={"Country": "Country_producer"})
    out.insert(0, "year", Y)
    db1 = out[["year", "fid", "longitude", "latitude", "crop", "lf_class", "Country_producer",
               "CF", "Fraction_N_marine", "cid", "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m",
               "crop_leaching_MtN", "N_reaching_MtN", "eutrophication"]]
    db1.to_csv(os.path.join(OUTDIR, "crop_eutrophication_%d.csv" % Y), index=False)
    rtxt = ("%.3f" % db1["N_reaching_MtN"].sum()) if db1["N_reaching_MtN"].notna().any() else "n/a"
    print("%d : DB1 cell-rows=%8d | placed=%6.3f of IMAGE %6.3f Tg N (%.0f%%) | reaching sea=%s Tg N | eutrophication(kg O2)=%.4e"
          % (Y, len(db1), db1["crop_leaching_MtN"].sum(), box["L_box"].sum(),
             100 * db1["crop_leaching_MtN"].sum() / box["L_box"].sum(), rtxt, db1["eutrophication"].sum()))

    # ---- DATABASE 2 : receptor attribution -- ARTIFICIAL split by EEZ coverage of the LME ---------
    #   Assumption: the impact is spread uniformly over the LME, so each cell's eutrophication is
    #   divided among the countries whose EEZ makes up that LME, by their area share. A MODELLING
    #   CHOICE - only the eutrophication is split (not the leaching, a land quantity). Each DB1 row
    #   is EXPANDED into one row per receptor country.
    #
    #   THE MERGE (the geographic attribution):
    #     db1  [key = LME_nb_f_1]   x   lme_ctry [LME_nb_f_1 -> receptor_country, area_portion]
    #     how="inner"  -> a cell whose LME touches N countries becomes N rows.
    #     lme_psum     = each LME's TOTAL covered fraction; w = area_portion / max(1, sum) renormalises
    #                    disputed LMEs (sum>1) so the split never exceeds 100%.
    #     ABNJ row     = the uncovered remainder (sum<1) as one 'High seas (ABNJ)' row, so the
    #                    per-cell eutrophication is conserved exactly (DB2 rows sum to the DB1 value).
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
    db2 = db2[["year", "fid", "longitude", "latitude", "crop", "lf_class", "Country_producer",
               "CF", "cid", "BasinID", "LME_nb_f_1", "LME_NAME", "dist_m", "Country_LME",
               "eutrophication"]]
    db2.to_csv(os.path.join(OUTDIR, "crop_eutrophication_LMEcountry_%d.csv" % Y), index=False)
    print("       DB2 receptor-rows=%8d (producer x LME-country) | conserved=%.4e kg O2 -> crop_eutrophication_LMEcountry_%d.csv"
          % (len(db2), db2["eutrophication"].sum(), Y))

ds.close()
print("DONE -- per-year crop files written to", OUTDIR)
