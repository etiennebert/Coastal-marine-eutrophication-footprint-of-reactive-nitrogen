# -*- coding: utf-8 -*-
"""
adalibieke_to_long_csv.py
Build the ONE missing pipeline input:  3_outputs/adalibieke_crop_N_long.csv
  columns -> longitude, latitude, crop, Nsyn, Nman
  (5 arcmin grid, year 2010, N as an AMOUNT in kg N per cell)

WHAT IT DOES  (flat: one step after another, no hidden/nested functions)
  For each Adalibieke per-crop file  'N_application_rate_<Crop>_1961-2020.h5':
     Nsyn_rate = sum of the 11 SYNTHETIC fertilizer forms (deep + surface)  [kg N / ha]
     Nman_rate = the MA (manure) form (deep + surface)                      [kg N / ha]
     Nsyn = Nsyn_rate * harvested_area      Nman = Nman_rate * harvested_area   [kg N / cell]
  Then stack every crop into one long table and save it.

WHY crop residue (CR) is EXCLUDED
  These Nsyn/Nman are only WEIGHTS used to split IMAGE-GNM's leaching flow.
  IMAGE-GNM's cropland N budget (which fixes the leaching magnitude) counts
  synthetic fertilizer and manure as inputs but NOT crop-residue recycling
  ("IMAGE-GNM does not provide this information"). To stay consistent with what
  we are splitting, the weights use synthetic + manure only. The third Adalibieke
  stream, CR (crop residue), is therefore left out on purpose.

WHY multiply by harvested area at all
  The pipeline normalises these weights inside each 0.5 deg IMAGE box, so their
  absolute units cancel. But area still matters: a high rate on a tiny field must
  receive less of the box's leaching than the same rate on a large field.

Requires: numpy, pandas, h5py.
"""
import os
import glob
import numpy as np
import pandas as pd
import h5py

# anchor relative paths to the PROJECT ROOT (folder holding 2_scripts/), any launch dir
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ============================ PARAMETERS (edit these) ============================
DOWNLOAD_DIR = "2. N_application_rate"                                  # where the .h5 files live
AREA_FILE    = "2. N_application_rate/Harvested_area_1961-2020.h5"      # per-crop harvested area (ha)
YEAR         = 2010
OUT_CSV      = "5. Outputs/adalibieke_crop_N_long.csv"

SYNTH_FORMS  = ["AA", "AN", "AS", "CAN", "NS", "ONS", "Urea", "AP", "NK", "NPK", "ONP"]  # 11 synthetic forms
MANURE_FORM  = "MA"      # manure
# RESIDUE_FORM = "CR"    # crop residue - EXCLUDED on purpose (see header)
# ================================================================================

YEAR_INDEX = YEAR - 1961     # the .h5 files cover 1961..2020 on axis 0
NCOL = 4320                  # 5 arcmin grid is 4320 lon x 2160 lat
NROW = 2160

# ---- STEP 1: find the per-crop N application files ------------------------------
files = sorted(glob.glob(os.path.join(DOWNLOAD_DIR, "N_application_rate_*_1961-2020.h5")))
print("STEP 1  found", len(files), "crop file(s)")
for f in files:
    print("   ", os.path.basename(f))
if not files:
    raise SystemExit("No N_application_rate_*.h5 files found - finish the download first.")
if len(files) < 21:
    print("   NOTE: only", len(files), "of 21 crops present - the download is not finished yet.")

# ---- STEP 2: open the harvested-area file (one dataset per crop, units = ha) -----
print("STEP 2  open harvested-area file:", AREA_FILE)
try:
    area_h5 = h5py.File(AREA_FILE, "r")
except Exception as e:
    raise SystemExit(
        "Could not open the harvested-area file (" + str(e) + ").\n"
        "It is probably still downloading / truncated. Re-run download_adalibieke_ftp.py\n"
        "until Harvested_area_1961-2020.h5 is complete (~2.8 GB), then run this script again."
    )
area_keys = list(area_h5.keys())
print("   area datasets (crops):", len(area_keys))

# ---- STEP 3: per crop -> Nsyn and Nman AMOUNT per 5 arcmin cell ------------------
rows = []
for f in files:
    crop = os.path.basename(f).replace("N_application_rate_", "").replace("_1961-2020.h5", "")
    try:
        h = h5py.File(f, "r")
    except Exception as e:
        raise SystemExit("Could not open " + os.path.basename(f) + " (" + str(e) + ").\n"
                         "That crop file is probably still downloading (truncated). Finish the\n"
                         "download with download_adalibieke_ftp.py, then run this script again.")
    present = set(h.keys())

    # synthetic rate = sum of the 11 forms, deep + surface (kg N / ha)
    nsyn_rate = np.zeros((NCOL, NROW), dtype=np.float64)
    for form in SYNTH_FORMS:
        for place in ("_deep", "_surface"):
            name = form + place
            if name in present:
                nsyn_rate += np.nan_to_num(h[name][YEAR_INDEX, :, :].astype(np.float64), nan=0.0)

    # manure rate = MA deep + surface (kg N / ha)
    nman_rate = np.zeros((NCOL, NROW), dtype=np.float64)
    for place in ("_deep", "_surface"):
        name = MANURE_FORM + place
        if name in present:
            nman_rate += np.nan_to_num(h[name][YEAR_INDEX, :, :].astype(np.float64), nan=0.0)
    h.close()

    # harvested area for this crop (ha); match the area dataset name case-insensitively
    match = [k for k in area_keys if k.lower() == crop.lower()]
    if not match:
        print("   WARNING: no harvested-area dataset named like '" + crop + "' - skipping this crop")
        continue
    area = np.nan_to_num(area_h5[match[0]][YEAR_INDEX, :, :].astype(np.float64), nan=0.0)  # (4320, 2160), ha

    # rate (kg/ha) x area (ha) = amount (kg N) per cell
    nsyn = nsyn_rate * area
    nman = nman_rate * area

    # keep only cells that actually carry some N
    keep = (nsyn + nman) > 0
    col_i, row_i = np.where(keep)          # axis0 = lon column, axis1 = lat row
    lon = -180.0 + (col_i + 0.5) / 12.0    # 5 arcmin cell centres
    lat = 90.0 - (row_i + 0.5) / 12.0
    sub = pd.DataFrame({"longitude": lon, "latitude": lat, "crop": crop,
                        "Nsyn": nsyn[keep], "Nman": nman[keep]})
    rows.append(sub)
    print("   " + crop.ljust(14) + " cells=" + str(len(sub)).rjust(8) +
          "  Nsyn=" + format(sub["Nsyn"].sum(), ".3e") +
          "  Nman=" + format(sub["Nman"].sum(), ".3e") + "  kg N")

area_h5.close()

# ---- STEP 4: stack all crops into one long table and save -----------------------
out = pd.concat(rows, ignore_index=True)
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
out.to_csv(OUT_CSV, index=False)
print("STEP 4  wrote", OUT_CSV, "->", len(out), "rows,", out["crop"].nunique(), "crop(s)")

# also write a small per-crop summary you can open and eyeball (one row per crop)
summary = out.groupby("crop").agg(cells=("crop", "size"),
                                  Nsyn_kgN=("Nsyn", "sum"),
                                  Nman_kgN=("Nman", "sum")).reset_index()
summary.to_csv("5. Outputs/adalibieke_crop_N_summary.csv", index=False)
print("   per-crop check table -> 5. Outputs/adalibieke_crop_N_summary.csv")
print("   global Nsyn =", format(out["Nsyn"].sum(), ".4e"), "kg N  |  global Nman =",
      format(out["Nman"].sum(), ".4e"), "kg N")
print("   NOTE verify harvested-area units (ha assumed): all-crop synthetic should land near ~9e10 kg N (~90 Tg).")
print("   These totals are only WEIGHTS; the leaching magnitude is fixed by IMAGE inside the pipeline.")
