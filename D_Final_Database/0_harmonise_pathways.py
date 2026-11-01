# 0_harmonise_pathways.py
# ---------------------------------------------------------------------------
# HARMONISATION LAYER: stack all four pathways into ONE comparable table.
#
#   READ-ONLY on every existing output - nothing upstream is modified or
#   duplicated. This script aggregates:
#     crop     A_agricultural_leaching/5. outputs_crops/crop_eutrophication_<year>.csv
#     grazing  A_agricultural_leaching/6. outputs_grazing/grazing_eutrophication_<year>.csv
#     NH3      B_airborne_NH3/3. Output/1_impact_tables/NH3_impact_country_to_LME.csv
#     NOx      C_airborne_NOx/3. Output/1_impact_tables/NOx_impact_country_to_LME.csv
#   into  eutrophication_all_pathways.parquet  (in THIS folder, D_Final_Database)
#
#     pathway | substance | year | emission_country | activity_type | activity |
#     LME_nb_f_1 | release_kg | release_kgN | delivered_kgN | CF_kgO2_per_kg | CF_kgO2_per_kgN | eutrophication_kgO2
#
#   HARMONISED ON PURPOSE:
#     - activity      = crop name / 'grazing' / IPCC sector  (activity_type says which)
#     - release_kg    = kg N leached (agriculture) or kg NH3 / kg NOx emitted (air)
#     - release_kgN   = everything as kg N:  leached N x1, NH3 x14/17, NOx x14/46
#                       (EDGAR reports NOx as NO2 - standard convention)
#     - LME labels    : air single-segment LMEs 'X_0' -> 'X' (shapefile convention)
#     - aviation typo : legacy NOx '1A31a' -> '1A3a' (if the old table is read)
#     - country names : air uses the EEZ union's SOVEREIGN1 spelling; agriculture
#                       uses World_Countries. An alias map reconciles the known
#                       differences; anything still unmatched is REPORTED, not dropped.
#   CF_kgO2_per_kg  = eutrophication / release_kg   (EFFECTIVE ratio per kg of the RELEASED species:
#                     kg N for leaching, kg NH3 / kg NO2 for air - not comparable across pathways)
#   CF_kgO2_per_kgN = eutrophication / release_kgN  (per kg N - comparable across all pathways)
#     - delivered_kgN = the N actually ENTERING the receiving water. For crop/grazing it is
#       the pipelines' N_reaching_MtN column (leaching x Fraction_N_marine, per-BASIN marine
#       tail from FFmar_XF_basin.csv) summed like the other columns - so the leaching DB1s
#       must have been produced by the updated pipelines, else the column is NaN. For the AIR
#       pathways it stays NaN: their marine tails are cell-level and cannot be recovered at
#       (country x sector x LME) level. release_kgN - delivered_kgN = the transport loss.
#
# HOW TO RUN: whole file, or cell-by-cell ('# %%'). Runtime is dominated by
# streaming the large crop CSVs (a few minutes). Needs pandas (+ pyarrow for parquet).
# ---------------------------------------------------------------------------

# %% imports + locations
import os
import glob
import numpy as np
import pandas as pd

try:
    HERE = os.path.dirname(os.path.abspath(__file__))       # ...\D_Final_Database
except NameError:
    HERE = os.getcwd()

ROOT   = os.path.dirname(HERE)                          # ...\Supporting_Information
A_DIR  = os.path.join(ROOT, "A_agricultural_leaching")
B_DIR  = os.path.join(ROOT, "B_airborne_NH3")
C_DIR  = os.path.join(ROOT, "C_airborne_NOx")
OUTDIR = HERE                                           # outputs live HERE, in D_Final_Database

YEARS      = list(range(2015, 2023))
KG_PER_MT  = 1e9            # agriculture leaching is in Mt N
N_IN_NH3   = 14.0 / 17.0    # kg N per kg NH3
N_IN_NO2   = 14.0 / 46.0    # kg N per kg NOx (EDGAR mass is 'as NO2')

# air country spelling (EEZ union SOVEREIGN1)  ->  World_Countries spelling
COUNTRY_ALIAS = {                     # verified against 5_LME_Country_match naming
    "Federal Republic of Somalia": "Somalia",
    "Republic of the Congo": "Congo",
    "Comores": "Comoros",
    "Saint Vincent and the Grenadines": "St. Vincent and the Grenadines",
    "Saint Lucia": "St. Lucia",
    "Grand Duchy of Luxembourg": "Luxembourg",
    "Republic of Mauritius": "Mauritius",
    "Saint Kitts and Nevis": "St. Kitts and Nevis",
}   # anything else that differs shows up in the printed report -> extend here
def fix_country(s):
    return s.replace(COUNTRY_ALIAS)

def first_existing(cands, what):
    for c in cands:
        if os.path.exists(c):
            return c
    print("  !! %s not found (skipped); tried: %s" % (what, "; ".join(cands)))
    return None

frames = []

# %% 1) AGRICULTURE (crop + grazing): stream each year's DB1, aggregate cell -> country x activity x LME
#   The 5 arcmin cell detail stays in the source files; here each cell's leaching and
#   eutrophication are summed into its (producer country, activity, LME) bucket.
for pathway, sub_dir, fname, act_col in [
        ("crop",    "5. outputs_crops",   "crop_eutrophication_%d.csv",    "crop"),
        ("grazing", "6. outputs_grazing", "grazing_eutrophication_%d.csv", None)]:
    leach_col = "crop_leaching_MtN" if pathway == "crop" else "grazing_leaching_MtN"
    for Y in YEARS:
        f = first_existing([os.path.join(A_DIR, sub_dir, fname % Y)], "%s %d" % (pathway, Y))
        if f is None:
            continue
        usecols = ["Country_producer", "LME_nb_f_1", leach_col, "eutrophication"]
        if act_col:
            usecols.insert(1, act_col)
        has_reach = "N_reaching_MtN" in pd.read_csv(f, nrows=0).columns  # updated pipelines only
        vals = [leach_col, "eutrophication"] + (["N_reaching_MtN"] if has_reach else [])
        keys = ["Country_producer"] + ([act_col] if act_col else []) + ["LME_nb_f_1"]
        parts = []
        for ch in pd.read_csv(f, usecols=usecols + (["N_reaching_MtN"] if has_reach else []),
                              dtype={"LME_nb_f_1": str}, chunksize=5_000_000):
            ch = ch.dropna(subset=["LME_nb_f_1"])
            parts.append(ch.groupby(keys, as_index=False)[vals].sum(min_count=1))
        if not parts:
            continue
        d = (pd.concat(parts, ignore_index=True)
               .groupby(keys, as_index=False)[vals].sum(min_count=1)
               .rename(columns={leach_col: "MtN", "eutrophication": "eutro"}))
        d["pathway"]   = pathway
        d["substance"] = "N_leached"
        d["year"]      = Y
        d["activity_type"] = "crop" if act_col else "pasture"
        d["activity"]  = d[act_col] if act_col else "grazing"
        d["release_kg"]  = d["MtN"] * KG_PER_MT          # kg N leached
        d["release_kgN"] = d["release_kg"]               # already nitrogen
        d["delivered_kgN"] = d["N_reaching_MtN"] * KG_PER_MT if has_reach else np.nan   # N entering the water
        d = d.rename(columns={"Country_producer": "emission_country",
                              "eutro": "eutrophication_kgO2"})
        frames.append(d[["pathway", "substance", "year", "emission_country", "activity_type",
                         "activity", "LME_nb_f_1", "release_kg", "release_kgN", "delivered_kgN",
                         "eutrophication_kgO2"]])
        print("%-8s %d : %6d (country x activity x LME) rows | %.3e kg O2" %
              (pathway, Y, len(d), d["eutrophication_kgO2"].sum()))

# %% 2) AIR (NH3 + NOx): the impact tables are already country x sector x LME - normalise and stack
#   Legacy tolerance: the pre-update NOx table has the '1A31a' aviation label and may lack
#   the emission_kg column - both handled (labels corrected; missing emissions -> NaN release).
for pathway, dir_, nfac in [("NH3", B_DIR, N_IN_NH3), ("NOx", C_DIR, N_IN_NO2)]:
    f = first_existing([os.path.join(dir_, "3. Output", "1_impact_tables", "%s_impact_country_to_LME.csv" % pathway),
                        os.path.join(dir_, "%s_impact_country_to_LME.csv" % pathway)],
                       pathway + " impact table")
    if f is None:
        continue
    d = pd.read_csv(f)
    d["IPCC_sector"] = d["IPCC_sector"].replace("1A31a", "1A3a")            # legacy typo
    d["LME_nb_f_1"]  = d["LME_nb_f_1"].astype(str).str.replace(r"_0$", "", regex=True)
    d["emission_country"] = fix_country(d["emission_country"])
    # impact is per source x receptor pair -> summing over pairs is correct
    g = (d.groupby(["year", "emission_country", "IPCC_sector", "LME_nb_f_1"], as_index=False)
           [["impact_kgO2"]].sum())
    # RELEASE must come from the DEDUPLICATED source table (one row per year x
    # country x sector). The pair table repeats the source emission on every
    # receptor row (~305 LMEs), so summing it over pairs inflates release ~305x.
    sf = first_existing([os.path.join(dir_, "3. Output", "1_impact_tables", "%s_impact_by_country_sector.csv" % pathway),
                         os.path.join(dir_, "%s_impact_by_country_sector.csv" % pathway)],
                        pathway + " source table")
    src = pd.read_csv(sf)
    ecol = [c for c in src.columns if c.startswith("emission_kg")][0]
    src["IPCC_sector"] = src["IPCC_sector"].replace("1A31a", "1A3a")
    src["emission_country"] = fix_country(src["emission_country"])
    src = (src.groupby(["year", "emission_country", "IPCC_sector"], as_index=False)
              .agg(E_src=(ecol, "sum"), I_src=("impact_kgO2_caused", "sum")))
    g = g.merge(src, on=["year", "emission_country", "IPCC_sector"], how="left")
    g["emission_kg"] = g["E_src"] * g["impact_kgO2"] / g["I_src"]   # apportioned by impact share
    g = g.drop(columns=["E_src", "I_src"])
    g["pathway"]       = pathway
    g["substance"]     = pathway
    g["activity_type"] = "IPCC_sector"
    g = g.rename(columns={"IPCC_sector": "activity", "impact_kgO2": "eutrophication_kgO2",
                          "emission_kg": "release_kg"})
    g["release_kgN"] = g["release_kg"] * nfac
    g["delivered_kgN"] = np.nan     # air marine tails are cell-level; not recoverable at pair level
    frames.append(g[["pathway", "substance", "year", "emission_country", "activity_type",
                     "activity", "LME_nb_f_1", "release_kg", "release_kgN", "delivered_kgN",
                     "eutrophication_kgO2"]])
    print("%-8s     : %7d rows | %.3e kg O2" % (pathway, len(g), g["eutrophication_kgO2"].sum()))

# %% 3) stack, effective CF, country-name check, save
if not frames:
    raise SystemExit("No pathway data found - run the pipelines first.")
H = pd.concat(frames, ignore_index=True)
H["CF_kgO2_per_kg"]  = H["eutrophication_kgO2"] / H["release_kg"]
H["CF_kgO2_per_kgN"] = H["eutrophication_kgO2"] / H["release_kgN"]

# delivered_kgN was filled per pathway above: agriculture from the pipelines' N_reaching_MtN
# (per-basin marine tail), air = NaN by construction.
if H["delivered_kgN"].notna().any():
    print("delivered_kgN: agriculture rows filled (from the pipelines' N_reaching_MtN)")
else:
    print("NOTE: delivered_kgN all NaN - re-run the leaching pipelines with "
          "'3. CFs/FFmar_XF_basin.csv' (c_make_FFmar_XF_basin.py) first")

H = H[["pathway", "substance", "year", "emission_country", "activity_type", "activity",
       "LME_nb_f_1", "release_kg", "release_kgN", "delivered_kgN", "CF_kgO2_per_kg", "CF_kgO2_per_kgN",
       "eutrophication_kgO2"]]

# country-name reconciliation report: air names that never appear on the agriculture side
ag  = set(H.loc[H["pathway"].isin(["crop", "grazing"]), "emission_country"].dropna())
air = set(H.loc[H["pathway"].isin(["NH3", "NOx"]), "emission_country"].dropna())
only_air = sorted(air - ag - {"High seas (ABNJ)"})
if only_air:
    print("\nCountry names on the AIR side with no agriculture match (%d) - fine for ocean/small" % len(only_air))
    print("states, but extend COUNTRY_ALIAS if a big emitter appears here:")
    print("  " + "; ".join(only_air[:25]) + (" ..." if len(only_air) > 25 else ""))

try:
    H.to_parquet(os.path.join(OUTDIR, "eutrophication_all_pathways.parquet"),
                 compression="zstd", index=False)
    outname = "eutrophication_all_pathways.parquet"
except Exception:
    H.to_csv(os.path.join(OUTDIR, "eutrophication_all_pathways.csv.gz"),
             index=False, compression="gzip")
    outname = "eutrophication_all_pathways.csv.gz (pyarrow missing)"

summary = (H.groupby(["pathway", "year"], as_index=False)
             .agg(rows=("eutrophication_kgO2", "size"),
                  release_kgN=("release_kgN", "sum"),
                  delivered_kgN=("delivered_kgN", lambda s: s.sum(min_count=1)),
                  eutrophication_kgO2=("eutrophication_kgO2", "sum")))
summary.to_csv(os.path.join(OUTDIR, "summary_pathway_year.csv"), index=False)

print("\n== HARMONISED: %d rows -> D_Final_Database/%s" % (len(H), outname))
print(summary.pivot(index="year", columns="pathway", values="eutrophication_kgO2")
             .to_string(float_format=lambda v: "%.3e" % v))
print("\nConservation: totals above must equal each pathway's own outputs; agriculture")
print("rows exclude cells with no LME (open-ended basins) exactly as the source files do.")
