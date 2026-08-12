# 0_prepare_EDGAR_emissions.py
# ---------------------------------------------------------------------------
# ONE preparation script for BOTH airborne emission databases (NH3 and NOx).
#
#   raw EDGAR v8.1 sector files            this script                 apply scripts
#   (per year x sector .txt, tonnes)  -->  parse + label + merge  -->  NH3_EDGAR_2015_2022.parquet
#   in  "1. EDGAR..." of B_ / C_          + write Parquet             NOx_EDGAR_2015_2022.parquet
#
# WHAT IT DOES (per substance)
#   1) find the raw folder ("<n>. EDGAR*" inside B_airborne_NH3 / C_airborne_NOx)
#   2) for every  v8.1_FT2022_AP_<sub>_<year>_<TAG>.txt :
#        - year   = the _YYYY_ in the name
#        - sector = SECTOR_MAP[TAG before '#']   (the LEGACY label, see below)
#        - data   = lat;lon;emission  (2 metadata lines, then a header line)
#   3) files that share one label (aviation CDS+CRS+LTO; NOx IRO+NFE -> '2C')
#      are MERGED: groupby (lat, lon) summing the emission - the same cell can
#      appear in several source files.
#   4) write one Parquet per substance, columns EXACTLY like the legacy CSVs:
#        Year, lat, lon, element, IPCC, emission        (emission in TONNES)
#      one row-group per year -> the apply scripts stream it year-block-wise.
#
# WHY PARQUET
#   The legacy CSVs are ~3.0 / 2.7 GB; Parquet (zstd, dictionary-encoded) holds
#   the identical table in a fraction of the space and reads faster. The apply
#   scripts accept BOTH (parquet preferred, legacy CSV as fallback), so nothing
#   breaks while you compare. Needs pyarrow:  conda install -c conda-forge pyarrow
#
# SECTOR LABELS -- reproduced from the LEGACY databases ON PURPOSE
#   The legacy NH3 and NOx CSVs use DIFFERENT label conventions for the same
#   EDGAR sectors (they were built at different times). These quirks are kept
#   so every downstream file keeps identical sector names:
#     - aviation merged 3 files -> label '1A3a' for BOTH substances. The legacy NOx
#       CSV wrote '1A31a' (a typo) - CORRECTED here; VERIFY maps it to '1A3a', but any
#       downstream table keyed on '1A31a' (e.g. folder E GLORIA workflows) must follow.
#     - agricultural soils AGS  -> NH3 '3C2_3C3_3C4_3C7'  but NOx '3C'
#     - agric. waste burning AWB-> NH3 '3C1'              but NOx '3C1b'
#     - road transport TRO      -> '1A3b_noRES' (EDGAR TRO excludes resuspension)
#     - REF_TRF's long tag      -> shortened '1A1b_1A1ci_1A1cii_1B1_1B2'
#
# VERIFIED against the legacy CSVs (this machine, full scan, all 8 years):
#   NH3: 84,436,352 rows, 17 labels; per-(year,label) sums match rel<=1e-10
#   NOx: 79,899,272 rows, 17 labels; per-(year,label) sums match rel<=2e-7
#   merged-label row counts match the legacy grouping exactly
#   (e.g. 2015 NOx '2C': 91,576 raw rows -> 91,170 grouped = legacy count).
#   The VERIFY cell at the end re-runs this comparison on your machine.
#
# HOW TO RUN:  whole file (F5), or cell-by-cell with the "# %%" cells.
# Env: pandas + pyarrow  (numpy comes with pandas)
# ---------------------------------------------------------------------------

# %% imports + configuration  (paths resolve relative to THIS file)
import os
import re
import glob
import numpy as np
import pandas as pd

try:
    HERE = os.path.dirname(os.path.abspath(__file__))       # ...\Supporting_Information
except NameError:                                           # cell-by-cell in Spyder
    HERE = os.getcwd()

YEARS   = list(range(2015, 2023))
YEAR_RE = re.compile(r"_(20\d\d)_")

# the two substances, their folders, and where the prepared database goes
JOBS = [
    dict(sub="NH3", folder=os.path.join(HERE, "B_airborne_NH3"),
         out_name="NH3_EDGAR_2015_2022"),
    dict(sub="NOx", folder=os.path.join(HERE, "C_airborne_NOx"),
         out_name="NOx_EDGAR_2015_2022"),
]

# LEGACY sector labels, keyed by the filename part BEFORE '#'  (verified, see header)
SECTOR_MAP = {
 "NH3": {
    "AGS": "3C2_3C3_3C4_3C7", "AWB": "3C1", "CHE": "2B", "ENE": "1A1a",
    "IND": "1A2", "MNM": "3A2", "NMM": "2A", "PRU_SOL": "2D_2E_2F_2G",
    "RCO": "1A4_1A5", "REF_TRF": "1A1b_1A1ci_1A1cii_1B1_1B2",
    "SWD_INC": "4C", "SWD_LDF": "4A_4B",
    "TNR_Aviation_CDS": "1A3a", "TNR_Aviation_CRS": "1A3a", "TNR_Aviation_LTO": "1A3a",
    "TNR_Other": "1A3c_1A3e", "TNR_Ship": "1A3d", "TRO": "1A3b_noRES", "WWT": "4D"},
 "NOx": {
    "AGS": "3C", "AWB": "3C1b", "CHE": "2B", "ENE": "1A1a", "FOO_PAP": "2H",
    "IND": "1A2", "IRO": "2C", "NFE": "2C", "MNM": "3A2", "NMM": "2A",
    "PRO_FFF": "1B1_1B2_5B", "RCO": "1A4_1A5",
    "REF_TRF": "1A1b_1A1ci_1A1cii_1B1_1B2", "SWD_INC": "4C",
    "TNR_Aviation_CDS": "1A3a", "TNR_Aviation_CRS": "1A3a", "TNR_Aviation_LTO": "1A3a",
    "TNR_Other": "1A3c_1A3e", "TNR_Ship": "1A3d", "TRO": "1A3b_noRES"},
}

def find_raw_dir(folder):
    """The raw folder is '<n>. EDGAR*' inside the pathway folder (rename-proof)."""
    hits = sorted(glob.glob(os.path.join(folder, "[0-9]. EDGAR*")))
    hits = [h for h in hits if os.path.isdir(h)]
    if not hits:
        raise FileNotFoundError("no '<n>. EDGAR*' folder inside " + folder)
    return hits[0]

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAVE_PA = True
except ImportError:                       # graceful fallback -> csv.gz (bigger, still works)
    HAVE_PA = False
    print("WARNING: pyarrow not installed -> writing csv.gz instead of Parquet.")
    print("         For the compact format:  conda install -c conda-forge pyarrow")

print("HERE =", HERE)

# %% BUILD) parse raw txt -> per-year table -> stream to Parquet (one row-group per year)
#   Memory stays at ~one year (~10.5M rows). groupby(lat, lon, IPCC) merges the
#   multi-file labels; for single-file labels it is a no-op (cells are unique
#   within one raw file) - verified against the legacy row counts.
for job in JOBS:
    sub, folder = job["sub"], job["folder"]
    raw_dir = find_raw_dir(folder)
    smap = SECTOR_MAP[sub]
    files = sorted(glob.glob(os.path.join(raw_dir, "v8.1_*.txt")))
    print("\n=== %s : %d raw files in %s" % (sub, len(files), os.path.basename(raw_dir)))

    by_year = {}
    for f in files:
        b = os.path.basename(f)[:-4]
        m = YEAR_RE.search(b)
        if not m:
            continue
        y = int(m.group(1))
        if y not in YEARS:
            continue
        tag  = b.split("_%d_" % y, 1)[1]
        code = tag.split("#")[0]
        if code not in smap:
            raise KeyError("unmapped sector tag '%s' (file %s) - extend SECTOR_MAP" % (code, b))
        by_year.setdefault(y, []).append((f, smap[code]))

    out_base = os.path.join(folder, job["out_name"])
    writer, total = None, 0
    for y in sorted(by_year):
        parts = []
        for f, label in by_year[y]:
            d = pd.read_csv(f, sep=";", skiprows=2)          # line 3 'lat;lon;emission' = header
            d["IPCC"] = label
            parts.append(d)
        yr = (pd.concat(parts, ignore_index=True)
                .groupby(["lat", "lon", "IPCC"], as_index=False)["emission"].sum())
        yr.insert(0, "Year", np.int32(y))
        yr.insert(3, "element", sub)
        yr = yr[["Year", "lat", "lon", "element", "IPCC", "emission"]]
        total += len(yr)
        if HAVE_PA:
            tbl = pa.Table.from_pandas(yr, preserve_index=False)
            if writer is None:
                try:
                    writer = pq.ParquetWriter(out_base + ".parquet", tbl.schema, compression="zstd")
                except Exception:
                    writer = pq.ParquetWriter(out_base + ".parquet", tbl.schema, compression="snappy")
            writer.write_table(tbl)                          # one row-group per year
        else:
            yr.to_csv(out_base + ".csv.gz", index=False, mode=("w" if y == sorted(by_year)[0] else "a"),
                      header=(y == sorted(by_year)[0]), compression="gzip")
        print("   %d : %d files -> %8d rows | %s = %.6e t" % (y, len(by_year[y]), len(yr), sub, yr["emission"].sum()))
    if writer is not None:
        writer.close()
    out_file = out_base + (".parquet" if HAVE_PA else ".csv.gz")
    print("   TOTAL %s rows: %d  ->  %s  (%.0f MB)" % (sub, total, os.path.basename(out_file),
          os.path.getsize(out_file) / 1e6))

# %% VERIFY) new database vs the LEGACY csv - per (Year, IPCC) row counts and sums
#   Streams the legacy 3 GB csv in chunks; skipped automatically if the legacy
#   file is gone. PASS = identical row count AND sum agrees to rel 1e-6.
for job in JOBS:
    sub, folder = job["sub"], job["folder"]
    _cand = [os.path.join(folder, job["out_name"] + ".csv"),
             os.path.join(find_raw_dir(folder), job["out_name"] + ".csv"),
             os.path.join(folder, "0. Old", job["out_name"] + ".csv"),
             os.path.join(folder, "_to_delete", job["out_name"] + ".csv")]
    legacy = next((c for c in _cand if os.path.exists(c)), None)
    newf   = os.path.join(folder, job["out_name"] + (".parquet" if HAVE_PA else ".csv.gz"))
    if legacy is None:
        print("%s: legacy csv not found (root / raw folder / 0. Old / _to_delete) -> verification skipped" % sub)
        continue
    if not os.path.exists(newf):
        print("%s: new database not present -> run the BUILD cell first" % sub)
        continue
    print("\n=== VERIFY %s ===" % sub)
    if HAVE_PA:
        newdb = pd.read_parquet(newf, columns=["Year", "IPCC", "emission"])
    else:
        newdb = pd.read_csv(newf, usecols=["Year", "IPCC", "emission"])
    a = newdb.groupby(["Year", "IPCC"])["emission"].agg(["size", "sum"])
    del newdb
    chunks = []
    for ch in pd.read_csv(legacy, usecols=["Year", "IPCC", "emission"], chunksize=5_000_000):
        ch["IPCC"] = ch["IPCC"].replace("1A31a", "1A3a")   # legacy NOx aviation typo -> corrected label
        chunks.append(ch.groupby(["Year", "IPCC"])["emission"].agg(["size", "sum"]))
    b = (pd.concat(chunks).groupby(level=[0, 1]).sum())
    cmp = a.join(b, lsuffix="_new", rsuffix="_old", how="outer")
    cmp["rows_ok"] = cmp["size_new"] == cmp["size_old"]
    cmp["sum_ok"]  = (cmp["sum_new"] - cmp["sum_old"]).abs() <= 1e-6 * cmp["sum_old"].abs()
    bad = cmp[~(cmp["rows_ok"] & cmp["sum_ok"])]
    print("keys compared: %d | mismatches: %d" % (len(cmp), len(bad)))
    if len(bad):
        print(bad.to_string())
    else:
        print("PERFECTLY ALIGNED: every (Year, IPCC) row count and emission sum matches. ")
        print("You can now archive/delete the legacy %s (the apply script reads the parquet)." % os.path.basename(legacy))

print("\nDONE.")
