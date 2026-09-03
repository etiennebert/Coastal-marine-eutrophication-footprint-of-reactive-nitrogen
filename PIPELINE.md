# PIPELINE — run order from raw data to the MRIO satellites

Arrows = hard dependencies. Steps 2a/2b and 3a/3b are independent of each other.
Every script runs whole (F5 / `python …`) or cell-by-cell (`# %%`), and prints its
own conservation checks. All impacts in kg O₂-eq.

```
[0] one-off data preparation (already done, rerun only to rebuild inputs)
     A_agricultural_leaching/2. N_application_rate/a_download_adalibieke.py   (TPDC download)
     A_agricultural_leaching/3. CFs/b_make_CF_csv_from_tif.py                 (CF tif -> csv)
     B_…/1. EDGARv8.1_NH3emissions/EDGAR_NH3_extraction.py                    (zips -> txt)
     C_…/1. EDGAR_V8.1_NOx/EDGAR_NOx_extraction.py                            (zips -> txt)
     E_…/0. data_GLORIAv60/NH3|NOx_EDGAR_air_GLORIA60_extraction.m  (MATLAB; GLORIA60 vectors)

[1] 0_prepare_EDGAR_emissions.py                (repo root)
     raw EDGAR txt  ->  B/NH3_EDGAR_2015_2022.parquet + C/NOx_EDGAR_2015_2022.parquet
     (verified against the legacy CSVs; VERIFY cell prints PERFECTLY ALIGNED)

[2a] A_agricultural_leaching/1_crop_eutrophication_pipeline.py     (independent of [1])
[2b] A_agricultural_leaching/2_grazing_eutrophication_pipeline.py
     IMAGE-GNM x Adalibieke x Wang LFs x CF  ->  per-year DB1 (producer side) and
     DB2 (receptor countries) in "5. outputs_crops" / "6. outputs_grazing"

[3a] B_airborne_NH3/1_apply_NH3_CF_country_LME.py     (needs [1])
[3b] C_airborne_NOx/1_apply_NOx_CF_country_LME.py     (needs [1])
     EDGAR parquet x CF matrix  ->  "3. Output/" with 5 subfolders:
     1_impact_tables, 2_databases (DB1 + cell x country x sector DB2),
     3_receptor_countries, 4_per_cell_maps, 5_CF_layers   (see _README.txt there)

[4] D_Final_Database/0_harmonise_pathways.py          (needs [2] + [3])
     stacks crop / grazing / NH3 / NOx  ->  eutrophication_all_pathways.parquet
     (year x pathway x emission_country x activity x LME; release_kg, release_kgN,
      effective CF; prints the pathway x year totals pivot)

[5] E_MRIO_GLORIA_Satellites/0_build_MRIO_satellites.py   (needs [4])
     LINEAR script: five blocks behind RUN_* switches, prep -> water -> NH3 ->
     NOx -> verify  (relaunch any subset: `python 0_build_MRIO_satellites.py NOx verify`)
     ->  "1. GLORIAv60_Eutrophication_Satellites/": satellite_<flow>_<year>.mat / .npz  (sparse 305 LME rows
         x 39,360 GLORIA v60 columns, exact sequential order, industry side),
         satellite_row/column_labels.csv, satellite_excluded_<flow>.csv (ABNJ high
         seas + Antarctica - no GLORIA region), satellite_unmatched_<flow>.csv
         (mapping failures - a clean run leaves none), build_report.txt
     Two GLORIA60 NOx vectors are zero in every year 2015-2022 and are split
     with the matching NH3 vectors as proxy keys (REVIEW, EMPTY_LABEL_PROXY):
     '3C1b' (agric. waste burning -> key NH3 '3C1') and '2A' (mineral
     industry -> key NH3 '2A'). These are the only two all-zero labels.
     verify must print OK on every flow x year line.

```

Notes
- Re-running an upstream step invalidates everything below it - resume from there.
- The receptor-country tables ([2]/[3] DB2, folder 3_) rest on the flagged
  uniform-within-LME assumption; the satellites use only producer-side results.
- High-seas (ABNJ) and Antarctic-EEZ emissions are excluded from the satellites
  by design: GLORIA has no international-transport region (Regions sheet, its
  1A3d rows hold only the regionally-allocable share) and no Antarctica region.
  The excluded amounts are quantified per flow in satellite_excluded_<flow>.csv.
