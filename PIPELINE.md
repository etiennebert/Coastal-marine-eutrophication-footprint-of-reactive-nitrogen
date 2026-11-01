# PIPELINE: run order from raw data to the manuscript figures

Arrows show hard dependencies. Steps 2a/2b and 3a/3b are independent of each
other. Every Python script runs whole (F5 / `python …`) or cell by cell
(`# %%`), and prints its own conservation checks. All impacts are in kg O₂-eq.

```
[0] one-off data preparation (already done; rerun only to rebuild inputs)
     A_agricultural_leaching/2. N_application_rate/a_download_adalibieke.py   (TPDC download)
     A_agricultural_leaching/3. CFs/b_make_CF_csv_from_tif.py                 (CF tif -> csv)
     B_…/1. EDGARv8.1_NH3emissions/EDGAR_NH3_extraction.py                    (zips -> txt)
     C_…/1. EDGAR_V8.1_NOx/  NOx twin of the NH3 extraction (script not yet in this repo; same logic)
     C_…/2. CFs/CF_NOx.m  (MATLAB; atmospheric CF matrix, kg O2-eq per kg N emitted)
     E_…/0. data_GLORIAv60/NH3|NOx_EDGAR_air_GLORIA60_extraction.m  (MATLAB; GLORIA60 vectors)

[0b] A_agricultural_leaching/3. CFs/c_make_FFmar_XF_basin.py   (before [2])
     SOS_airgrid.xls -> FFmar_XF_basin.csv + FFmar_XF_subsegment.csv
     (marine tail of the arable CF; without it Fraction_N_marine / delivered N are NaN)

[1] 0_prepare_EDGAR_emissions.py                (repo root)
     raw EDGAR txt  ->  B/NH3_EDGAR_2015_2022.parquet + C/NOx_EDGAR_2015_2022.parquet
     (verified against the legacy CSVs; VERIFY cell prints PERFECTLY ALIGNED)

[2a] A_agricultural_leaching/1_crop_eutrophication_pipeline.py     (independent of [1])
     year-specific Adalibieke weights (2015-2020; 2020 reused for 2021-22),
     cached as "2. N_application_rate/adal_split_<year>_<area|rate>.parquet"
[2b] A_agricultural_leaching/2_grazing_eutrophication_pipeline.py
     IMAGE-GNM surplus x Adalibieke x Wang LFs x CF  ->  per-year DB1 (producer
     side, incl. Fraction_N_marine and N_reaching_MtN) and DB2 (receptor countries)
     in "5. outputs_crops" / "6. outputs_grazing"

[3a] B_airborne_NH3/1_apply_NH3_CF_country_LME.py     (needs [1])
[3b] C_airborne_NOx/1_apply_NOx_CF_country_LME.py     (needs [1])
     EDGAR parquet x CF matrix (per kg N, converted x14/17 and x14/46 to per kg
     NH3 / NO2 when read)  ->  "3. Output/" with 5 subfolders:
     1_impact_tables, 2_databases (DB1 + cell x country x sector DB2),
     3_receptor_countries, 4_per_cell_maps, 5_CF_layers   (see _README.txt there)

[4] D_Final_Database/0_harmonise_pathways.py          (needs [2] + [3])
     stacks crop / grazing / NH3 / NOx  ->  eutrophication_all_pathways.parquet
     (year x pathway x emission_country x activity x LME; release_kg, release_kgN,
      delivered_kgN, effective CFs; prints the pathway x year totals pivot)
[4b] D_Final_Database/1_Nleaching_country_tables.py   (optional; leaching tables)

[5] E_MRIO_GLORIA_Satellites/0_build_MRIO_satellites.py   (needs [4])
     LINEAR script, five blocks behind RUN_* switches: prep -> water -> NH3 ->
     NOx -> verify  (relaunch any subset: `python 0_build_MRIO_satellites.py NOx verify`)
     ->  "1. GLORIAv60_Eutrophication_Satellites/": satellite_<flow>_<year>.mat / .npz
         (sparse 305 LME rows x 39,360 GLORIA v60 columns, exact sequential order,
         industry side), satellite_row/column_labels.csv, satellite_excluded_<flow>.csv
         (ABNJ high seas + Antarctica, which have no GLORIA region),
         satellite_unmatched_<flow>.csv (mapping failures; a clean run leaves
         none), build_report.txt
     verify must print OK on every flow x year line.

[6] GLORIA-anchored batch                                    (needs [5])
     E_…/1_check_GLORIA_vs_EEZ_emissions.py   validation vs GLORIA's own accounts
     E_…/2_make_anchored_satellites.py        -> "1b. GLORIAv60_Eutrophication_Satellites_anchored/"
                                              (+ satellite_dship / dhh delta satellites)
     E_…/3_PBA_before_after_table.py          the Check sheet must be empty

[7] MATLAB  F_Practical_case/E_1_Consumption_eutrophication_LME.m   (needs [5]/[6] + GLORIA L)
     run twice: BATCH = 'original'  -> "1. results/"
                BATCH = 'anchored'  -> "1. results_anchored/"     (years 2015-2022)

[8] figures and tables (from F_Practical_case)
     python F_5_sector_tables_from_satellite.py            (original batch)
     python F_5_sector_tables_from_satellite.py anchored   (anchored batch)
     Rscript F_2_Figures_CBA_PBA.R      Figs 2-4 (ANCHORED switch: one batch for all three)
     python F_3_Figure1_map.py          Fig 1
     python F_4_Sankey_reef.py <year> anchored   (each year 2015-2022)
     python F_6_build_database.py <year>  ->  Rscript F_7_climate_sector_flow.R
     node make_table1.js                Table 1
```

Notes
- Rerunning an upstream step invalidates everything below it; resume from there.
  After the November 2026 units fix, rerun [3] -> [8].
- The receptor-country tables ([2]/[3] DB2, folder 3_) rest on the flagged
  uniform-within-LME assumption; the satellites use only producer-side results.
- High-seas (ABNJ) and Antarctic-EEZ emissions are excluded from the satellites
  by design: GLORIA has no international-transport region (Regions sheet; its
  1A3d rows hold only the regionally allocable share) and no Antarctica region.
  The excluded amounts are quantified per flow in satellite_excluded_<flow>.csv.
- Two GLORIA60 NOx vectors are zero in every year 2015-2022 and are split with
  the matching NH3 vectors as proxy keys (REVIEW, EMPTY_LABEL_PROXY): '3C1b'
  (agricultural waste burning -> key NH3 '3C1') and '2A' (mineral industry ->
  key NH3 '2A').
- Paths default to this repository tree. Set EUTRO_MODEL_ROOT, EUTRO_SHAPES or
  GLORIA_ROOT to point to data stored elsewhere.
