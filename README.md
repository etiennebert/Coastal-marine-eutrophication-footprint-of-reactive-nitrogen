# Coastal marine eutrophication footprint of reactive nitrogen — model code (2015–2022)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21969820.svg)](https://doi.org/10.5281/zenodo.21969820)

Global model chain quantifying the coastal marine eutrophication impact of
reactive nitrogen reaching the ocean through three pathways — **agricultural
leaching** of waterborne N, **airborne NH₃**, and **airborne NOₓ** — for
**2015–2022**. Impacts are expressed in **kg O₂-eq** (marine oxygen depletion)
and resolved to 305 coastal **Large Marine Ecosystem sub-segments (cLME-ss)**
with the emitting country and driving activity attached, harmonised into one
comparable database, and converted into **GLORIA v60 MRIO satellite matrices**
(305 LME-ss rows × 39,360 region–sector columns per year and substance), ready
to be used as environmental extensions in GLORIA-based EE-MRIO analyses.

The framework builds on and couples the spatially differentiated
marine-eutrophication models of Cosme & Hauschild (2017), Cosme et al. (2018)
and Vea et al. (2022, 2024) — atmospheric characterisation following Bjørn et
al. (2020) — with the IMAGE-GNM global nutrient model (Beusen et al., 2015),
EDGAR v8.1 gridded emissions (Crippa et al., 2024), the crop-specific
fertilisation dataset of Adalibieke et al. (2023), and the GLORIA v60 MRIO
(University of Sydney IELab). Full citations are on the Zenodo record.

> [!IMPORTANT]
> **This repository tracks the code only.** The full working archive (~28 GB:
> input data, intermediate databases and results, minus the third-party
> datasets that cannot be redistributed) is deposited on Zenodo:
> **[doi:10.5281/zenodo.21969820](https://doi.org/10.5281/zenodo.21969820)** (concept DOI: always
> resolves to the latest version; v1.0.0 predates the fixes listed under *Changelog*).
> Pointer files inside the archive explain how to obtain each non-redistributed
> dataset (see [Data availability](#data-availability)).

---

## Repository layout

```
Supporting_Information/
├── PIPELINE.md                        run order + dependencies (the map of this repo)
├── run_pipeline.bat                   one-click sequential run of steps [0b]–[8] (Windows/conda)
├── LICENSE                            MIT (code)
├── .zenodo.json                       metadata of the Zenodo data deposit
│
├── 0_shape_files/                     shared GIS boundaries (shapefiles on Zenodo; the small
│                                      CSV/XLSX match tables and licences are tracked)
│   ├── 1_World_Countries/             country polygons
│   ├── 2_LME shape files/             LME sub-segments (cLME_ss_full)
│   ├── 3_BasinID_shape_PCR2/          PCR-GLOBWB river-basin IDs
│   ├── 5_LME_Country_match/           LME sub-segment ↔ country EEZ shares (validated;
│   │                                  LME_country_match.csv tracked - 305 labels incl. X_10)
│   ├── 6_EEZ_land_union_v3_202003/    EEZ–land union (SHARED by both air pipelines)
│   └── 0_gridcells_LME_mapped.csv     air-grid cell → LME map (SHARED, tracked)
│
├── A_agricultural_leaching/           waterborne-N cropland & grazing pathway (Python)
│   ├── 1_crop_eutrophication_pipeline.py     crop-disaggregated leaching -> LME
│   ├── 2_grazing_eutrophication_pipeline.py  grazing/pasture twin
│   ├── 2. N_application_rate/a_download_adalibieke.py   TPDC downloader (credentials NOT
│   │                                  included — request your own, see Security note)
│   ├── 3. CFs/b_make_CF_csv_from_tif.py      CF_arable_final.tif -> CF_arable.csv
│   ├── 3. CFs/c_make_FFmar_XF_basin.py       marine tail XF/removal per river basin (+ sub-segment
│   │                                  fallback) -> Fraction_N_marine / delivered N (run before [2])
│   ├── 1. Input_IMAGE_GNM/ · 2. N_application_rate/ · 3. CFs/   raw inputs (data;
│   │                                  _DATA_NOT_INCLUDED_README.txt says where to get them)
│   ├── 4. Leaching_factors/           Wang et al. 2025 leaching factors (tracked)
│   └── 5. outputs_crops/ · 6. outputs_grazing/   generated per-year DB1/DB2
│
├── 0_prepare_EDGAR_emissions.py       ONE prep script: raw EDGAR v8.1 txt -> both emission
│                                      Parquet databases (self-verifies vs the legacy CSVs)
│
├── B_airborne_NH3/                    NH₃ × atmospheric fate factors -> LME (Python)
│   ├── 1_apply_NH3_CF_country_LME.py  main pipeline (cell × country × sector × LME)
│   ├── 1. EDGARv8.1_NH3emissions/     raw EDGAR sector txt + extraction script (data)
│   ├── 2. CFs/CF_NHx_all.csv          source→receptor CF matrix, 2° grid (data)
│   ├── 3. Output/                     5 result subfolders + _README.txt (generated)
│   └── NH3_EDGAR_2015_2022.parquet    prepared emission database (generated)
│
├── C_airborne_NOx/                    NOₓ twin of B (Python; CF matrix built by CF_NOx.m)
│
├── D_Final_Database/                  the harmonisation layer
│   ├── 0_harmonise_pathways.py        READ-ONLY stack of crop/grazing/NH₃/NOₓ at
│   │                                  pathway × year × country × activity × LME
│   ├── 1_Nleaching_country_tables.py  leaching-only country × crop tables: N released / N reaching the sea
│   └── eutrophication_all_pathways.parquet   (generated)
│
├── E_MRIO_GLORIA_Satellites/          GLORIA v60 satellite builder (Python)
│   ├── 0_build_MRIO_satellites.py     LINEAR script, steps prep → water → NH3 → NOx → verify
│   ├── 1_check_GLORIA_vs_EEZ_emissions.py   validation of our EDGAR/EEZ emissions vs GLORIA's own
│   │                                  accounts (correlations, ratios, transit & household shares)
│   ├── 2_make_anchored_satellites.py  GLORIA-anchored batch: 1A3d (maritime) and 1A3b (road)
│   │                                  rescaled per country by rho = min(1, GLORIA/EDGAR); the excess is
│   │                                  kept as delta satellites dship (international shipping) and dhh
│   │                                  (household driving) -> "1b. …_anchored/"
│   ├── 3_PBA_before_after_table.py    7 reef sites × 120 sectors, original vs anchored PBA (check sheet)
    ├── 0. data_GLORIAv60/             GLORIA_ReadMe_060.xlsx, country→region map,
    │                                  crop→GLORIA-sector match, GLORIA60 per-label
    │                                  emission vectors (NH3/, NOx/ — the air
    │                                  disaggregation keys) + their MATLAB extraction scripts
    └── 1. GLORIAv60_Eutrophication_Satellites/    (generated)
                                       satellite_<flow>_<year>.mat/.npz — sparse 305 LME-ss
                                       rows × 39,360 GLORIA v60 columns in the exact
                                       sequential order, values on the industry side —
                                       plus satellite_row/column_labels.csv,
                                       satellite_excluded_<flow>.csv,
│                                      satellite_unmatched_<flow>.csv, build_report.txt
│
└── F_Practical_case/                  coral-reef case study (7 cLME-ss) and manuscript figures
    ├── E_1_Consumption_eutrophication_LME.m   MATLAB: PBA/CBA per sub-segment with GLORIA L
    │                                  (BATCH = 'original' | 'anchored', years 2015–2022)
    ├── F_2_Figures_CBA_PBA.R          Figs 2–4 (one ANCHORED switch for all three)
    ├── F_3_Figure1_map.py             Fig 1 map
    ├── F_4_Sankey_reef.py             producer→consumer Sankeys (python F_4_Sankey_reef.py <year> anchored)
    ├── F_5_sector_tables_from_satellite.py   PBA sector tables from satellite rows (no MATLAB)
    ├── F_6_build_database.py          one-year long database (LME, climate, country, sector, original vs anchored)
    ├── F_7_climate_sector_flow.R      climate-zone × sector group × pathway figure
    └── make_table1.js                 Table 1 (top producing countries per site)
```

Tracked in git: the `.py`/`.m`/`.R`/`.js`/`.bat` sources, `PIPELINE.md`, the Zenodo
metadata file, `Wang2025_leaching_factors.csv`, `MouthID_PCR2.csv`,
`0_gridcells_LME_mapped.csv`, `LME_country_match.csv`, and this README. Everything else (raw data,
shapefiles, `.h5`/`.nc`/`.tif`, Parquet/`.mat`/`.npz` outputs) is excluded by
`.gitignore` and lives in the Zenodo archive.

---

## Environment

Plain NumPy/pandas plus a few geospatial libraries; a conda-forge environment:

```bash
conda create -n geo2 -c conda-forge python=3.11 \
    numpy pandas scipy xarray netCDF4 h5netcdf h5py \
    geopandas shapely pyproj rasterio pyarrow openpyxl
conda activate geo2
```

(`run_pipeline.bat` activates an env named `geo2`; rename inside the .bat if
yours differs. `a_download_adalibieke.py` needs only the standard library.
MATLAB is needed only to rebuild two provenance inputs: the NOₓ CF matrix,
`CF_NOx.m`, and the GLORIA60 emission vectors, `*_GLORIA60_extraction.m` —
both ship pre-extracted in the data archive.)

Every script runs **either** whole (`python <script>.py` / F5) **or**
cell-by-cell (`# %%` cells), with plain inspectable variables — the code is
deliberately linear with as few functions as possible, so it can be reviewed
and debugged line by line.

---

## How to run

`PIPELINE.md` is the authoritative map; `run_pipeline.bat` executes [1]–[5]
sequentially with stop-on-error. In short:

1. **[1] `0_prepare_EDGAR_emissions.py`** (repo root) — parses the raw EDGAR
   v8.1 sector files into `NH3_/NOx_EDGAR_2015_2022.parquet` with the exact
   legacy sector labels, and verifies row counts and sums against the legacy
   extractions ("PERFECTLY ALIGNED").
2. **[2] `A_…/1_crop…` and `2_grazing…`** — split the IMAGE-GNM 0.5° leaching
   into 5-arcmin cells × crops (Adalibieke fertilisation × Wang leaching
   factors), apply the waterborne CF, aggregate river-basin → LME. Each writes
   a producer-side DB1 (per cell) and a receptor-country DB2 (flagged
   assumption, see below).
3. **[3] `B_…/1_apply_NH3…` and `C_…/1_apply_NOx…`** — multiply gridded EDGAR
   emissions by the atmospheric source→receptor CF matrix (2° grid; the CFs are
   **per kg N** and are converted to per kg NH₃ / NO₂ with ×14/17 and ×14/46 as
   they are read), map
   receptors to LME sub-segments, and aggregate by emitting country × IPCC
   sector × LME; also emit cell-level databases, receptor-country tables,
   per-cell maps and CF layers (see `3. Output/_README.txt`).
4. **[4] `D_…/0_harmonise_pathways.py`** — stacks all four pathways into
   `eutrophication_all_pathways.parquet`
   (`pathway | substance | year | emission_country | activity_type | activity |
   LME_nb_f_1 | release_kg | release_kgN | delivered_kgN | CF_kgO2_per_kg |
   CF_kgO2_per_kgN | eutrophication_kgO2`).
5. **[5] `E_…/0_build_MRIO_satellites.py`** — builds, per year × flow
   (N-leach, NH₃, NOₓ), a sparse **305 × 39,360** satellite in the exact GLORIA
   v60 sequential column order (values on the industry columns), saved as
   `.mat` + `.npz` in `1. GLORIAv60_Eutrophication_Satellites/`. Agriculture
   maps ~1:1 to GLORIA crop/cattle sectors; air IPCC sectors are split with
   GLORIA's own per-label emission vectors as region- and year-specific keys.
   Five blocks behind `RUN_*` switches — relaunch any subset, e.g.
   `python 0_build_MRIO_satellites.py NOx verify`. The `verify` step must
   print `OK` on every flow × year line (`build_report.txt`).

6. **[6] GLORIA-anchored batch** — `E_…/1_check…` (validation), `2_make_anchored…`,
   `3_PBA_before_after…`.
7. **[7] MATLAB `F_Practical_case/E_1…m`** — run twice, `BATCH = 'original'` and
   `BATCH = 'anchored'` (needs GLORIA `matrix calc`).
8. **[8] figures** — `F_5` (both batches), `F_2` (R), `F_3`, `F_4 <year> anchored`,
   `F_6 <year>` then `F_7` (R), `make_table1.js`.

Re-running an upstream step invalidates everything below it — resume from there.

The satellites then load directly for MRIO work, in MATLAB
(`d = load('satellite_NH3_2015.mat'); % d.S sparse 305×39360, d.LME_rows`) or
Python (`scipy.sparse.load_npz`), with the column order documented in
`satellite_column_labels.csv`.

---

## Method (short)

For each 0.5° IMAGE-GNM grid box the deposition-free agricultural N surplus `L_box`
(cropland; interpolated linearly between the 5-yearly IMAGE nodes, 2021–22 towards
the SSP2 2025 node) is split across the 5-arcmin cells and crops inside it by a
leaching-potential weight `P = Nsyn·LF_crop + Nman·LF_organic`, with `Nsyn`, `Nman`
= Adalibieke application rate × harvested area **of the same year** (2015–2020;
2021–2022 reuse the 2020 pattern), so `L(cell,crop) = L_box · P / ΣP`;
marine eutrophication is `E = L · 10⁹ · CF(cell)` with the waterborne-N
characterisation factor routed basin → river mouth → LME. Atmospheric
deposition is **removed** from the IMAGE surplus so the cropland pathway does
not double-count the airborne streams: NH₃ and NOₓ are treated separately by
applying a source→receptor atmospheric fate matrix (2° grid) to EDGAR v8.1
emissions and aggregating receptors to LME sub-segments. **Units:** the
atmospheric CFs are per kg N (Vea et al. 2024); since EDGAR reports kg NH₃ and kg
NOₓ as NO₂, the CF blocks are multiplied by 14/17 and 14/46 when read (runs before
November 2026 omitted this and overstated airborne impacts ×1.21 and ×3.29). For
reporting, the nitrogen reaching coastal water is diagnosed per cell as
`Fraction_N_marine = CF / (XF/removal)` (the marine tail of the arable CF chain,
from `SOS_airgrid.xls`, capped at 1). The **GLORIA-anchored** batch rescales
maritime (1A3d) and road (1A3b) emissions per country to GLORIA's activity-based
accounts and keeps the excess as international shipping and household driving
(separate delta satellites). The harmonised
database expresses all releases both in native mass and as kg N (NH₃ ×14/17,
NOₓ ×14/46 as NO₂). The satellite builder places each (country, activity, LME)
impact on the GLORIA v60 industry columns of the emitting region. All impacts
in **kg O₂-eq**.

## Modelling choices flagged `REVIEW` in the code

- **Receptor-country tables (DB2 / `3_receptor_countries`)** split each LME's
  impact over the countries whose EEZ composes it by validated area shares —
  this assumes impact spread uniformly within the LME. The satellites use only
  the producer-side (DB1) chain.
- **Empty GLORIA60 vectors — proxy split keys**: exactly two NOₓ labels have
  all-zero GLORIA60 emission vectors in every year (full scan, both
  substances): `3C1b` (agricultural waste burning) and `2A` (mineral
  industry). Their impacts are split with the matching NH₃ vectors of the same
  activities (`3C1`, `2A`) as proxy keys — configured in `EMPTY_LABEL_PROXY`,
  every use printed and counted.
- **High seas (ABNJ) and the Antarctic EEZ** are excluded from the satellites —
  GLORIA has no international-transport or Antarctica region — and quantified
  in `satellite_excluded_<flow>.csv`.
- The legacy NOₓ aviation label typo (`1A31a`) is corrected to `1A3a`
  throughout; `CF_kgO2_per_kg` (per kg released species) and `CF_kgO2_per_kgN`
  (per kg N, comparable across pathways) in the harmonised table are *effective*
  (result-side) ratios, not intrinsic fate factors.
- **Anchoring vintage**: `2_make_anchored_satellites.py` compares EDGAR v8.1 with
  GLORIA's own (older-vintage) EDGAR-based vectors without the vintage factor β
  that `1_check…` reports; any systematic version offset is booked as
  international shipping / household driving. Report β alongside the results.
- **Grazing**: all pasture N is attributed to GLORIA "Raising of cattle".

---

## Data availability

The exact input and output versions used are archived on Zenodo:
**[doi:10.5281/zenodo.21969820](https://doi.org/10.5281/zenodo.21969820)** (concept DOI).
Datasets that cannot be redistributed are replaced there by
`_DATA_NOT_INCLUDED_README.txt` pointer files; obtain them from their sources:

| Dataset | Used for | Source |
|---|---|---|
| Adalibieke crop-specific N fertilisation (+ harvested area), `*.h5` | crop weights `Nsyn/Nman` | TPDC, [doi:10.11888/Terre.tpdc.300446](https://doi.org/10.11888/Terre.tpdc.300446) — personal FTP credentials required (`a_download_adalibieke.py`) |
| IMAGE-GNM cropland/pasture N budgets (SSP2, oct2020, v2), `*.nc` | leaching magnitude `L_box` | INMS data portal (registered users), PBL — Beusen et al. (2015) |
| CF_arable (5-arcmin waterborne-N CF), `CF_arable_final.tif` | `CF(cell)` | Vea et al. (2022, 2024) |
| N leaching factors, `Wang2025_leaching_factors.csv` | `LF_crop`, `LF_organic` | Wang et al. (2025) — **in repo** |
| EDGAR v8.1 NH₃ / NOₓ gridded emissions | airborne source terms | EDGAR, EU JRC, `https://edgar.jrc.ec.europa.eu` (CC-BY 4.0) |
| Atmospheric source→receptor CF matrices, `CF_NHx_all.csv`, `CF_NOx_all.csv` (kg O₂-eq per kg **N** emitted) | airborne fate | generated (builder: `CF_NOx.m`; the NHx matrix comes from the same Vea et al. 2024 model, builder not included); method per Bjørn et al. (2020), Vea et al. (2024) |
| LME sub-segments, `cLME_ss_full.shp` | receptor aggregation | Vea et al. (2022) |
| EEZ / country polygons, EEZ–land union v3 (2020-03) | country tagging | Marine Regions, `https://marineregions.org` |
| River-basin IDs, `BasinID_PCR2.shp`, `MouthID_PCR2.csv` | basin → mouth → LME | PCR-GLOBWB ("PCR2") — mouth table **in repo** |
| GLORIA v60 MRIO (T, Y, satellites, ReadMe) | folder E labels + air split keys | University of Sydney IELab GLORIA release — **not redistributed**; register with IELab |

---

## Security note

`a_download_adalibieke.py` ships with **placeholder credentials only** and
refuses to run until you insert your own (or set `TPDC_USER` / `TPDC_PASS`):
TPDC issues personal FTP credentials per data request. Never commit real
credentials.

## License & citation

Code released under the **MIT License** (see `LICENSE`); the archived data on
Zenodo under **CC-BY 4.0**. If you use this code or the archived data, please cite
the Zenodo record:

> Berthet, E. C., & Blikra Vea, E. (2026). *Coastal marine eutrophication
> footprint of reactive nitrogen: global emission-to-impact model chain and
> GLORIA MRIO satellites (2015–2022)* [Data set]. Zenodo.
> [https://doi.org/10.5281/zenodo.21969820](https://doi.org/10.5281/zenodo.21969820)

Third-party datasets remain under the licenses of their original providers
(see [Data availability](#data-availability)).

## Contact

Etienne Berthet — MIT Center for Sustainability Science and Strategy,
Massachusetts Institute of Technology.

## Changelog

- **v1.1.0 (Nov 2026)**
  - **Units fix (airborne):** CFs per kg N are now converted to per kg NH₃ / NO₂ before
    being applied to EDGAR species mass (impacts were overstated ×1.21 for NH₃ and ×3.29 for NOₓ).
  - **Crop weights:** year-specific Adalibieke weights (2015–2020; 2020 for 2021–22), cached
    per year and weight mode, with a strict guard against rate-only drafts.
  - **Delivered N:** `Fraction_N_marine` / `delivered_kgN` (marine tail from `c_make_FFmar_XF_basin.py`).
  - **Harmonisation:** release de-duplication (the v1.0.0 database inflated airborne
    `release_kgN` ×305; impacts unaffected), extra country aliases, `CF_kgO2_per_kgN`.
  - **New scripts:** GLORIA-anchored satellite batch (E/1–3) and the `F_Practical_case`
    case-study and figure scripts (one accounting batch per run).
  - **Repository:** relative paths with environment-variable overrides; `LME_country_match.csv` tracked.
- **v1.0.0 (Aug 2026)** — initial release.
