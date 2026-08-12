# -*- coding: utf-8 -*-
"""
Created on Tue Aug 12 13:07:06 2025

@author: etber
"""

import re
import sys
from pathlib import Path
from zipfile import ZipFile, BadZipFile

# --- CONFIG ---
ROOT_DIR = Path(r"C:/Users/etber/OneDrive/Nitrogen_Paper/SI_1/0_External_data/2_EDGAR_data/NH3")      # folder that contains subfolders with zips
OUTPUT_DIR = Path(r"C:/Users/etber/OneDrive/Nitrogen_Paper/SI_1/0_External_data/2_EDGAR_data/NH3/NH3")  # where filtered, renamed files will go

# strict: underscore-bound year only
YEAR_RE = re.compile(r'_(2015|2016|2017|2018|2019|2020|2021|2022|2023)_')
# -----------------------------------

def matches_year_pattern(name: str) -> bool:
    """True iff filename contains _YYYY_ with YYYY in 2015..2023."""
    return YEAR_RE.search(name) is not None

def add_zip_suffix(fname: str, zip_stem: str) -> str:
    p = Path(fname)
    return f"{p.stem}#{zip_stem}{p.suffix}"

def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{i}{path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1

def main(root: Path, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    zips = list(root.rglob("*.zip"))
    if not zips:
        print(f"No zip files found under {root}")
        return

    for zpath in zips:
        zip_stem = zpath.stem
        try:
            with ZipFile(zpath) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    inner_name = Path(info.filename).name  # ignore inner dirs
                    if not inner_name:
                        continue
                    if not matches_year_pattern(inner_name):
                        # STRICT SKIP of non-matching files
                        continue
                    renamed = add_zip_suffix(inner_name, zip_stem)
                    dest = unique_path(outdir / renamed)
                    with zf.open(info) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
            print(f"Processed: {zpath}")
        except BadZipFile:
            print(f"Skipping corrupt zip: {zpath}", file=sys.stderr)

if __name__ == "__main__":
    main(ROOT_DIR, OUTPUT_DIR)