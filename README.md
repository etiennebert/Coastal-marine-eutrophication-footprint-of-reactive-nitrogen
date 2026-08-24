# Supporting Information — Coastal marine eutrophication footprint of reactive nitrogen

Analysis code and workflow for the Supporting Information of:

> **\<Authors\>, "\<Paper title\>", \<Journal\> (\<year\>). DOI: \<to be added\>**

<!-- Once the Zenodo record is published, put the badge here:
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX) -->

This repository quantifies the marine eutrophication impact of reactive
nitrogen reaching the ocean through three pathways — **agricultural leaching**
of waterborne N, **airborne NH₃**, and **airborne NOₓ** — for **2015–2022**,
resolves it to 305 **Large Marine Ecosystem (LME) sub-segments** (kg O₂-eq,
Cosme & Hauschild oxygen-depletion model), harmonises the three pathways into
one comparable database (folder D), converts them into **GLORIA v60 MRIO
satellite matrices** (folder E), and traces each LME's eutrophication back to
**final consumption**, including a coral-reef case study on seven LME
sub-segments (folder F, MATLAB).

> [!IMPORTANT]
> **Data are not stored in this repository.** The full working folder is
> ~28 GB and GitHub rejects any file larger than 100 MB. Only the code and a
> few small input tables are tracked here; every large dataset must be obtained
> from its original source or from the archived Zenodo deposit
> (DOI: *to be added* — see [Data availability](#data-availability)).

---

## Repository layout

```
Supporting_Information/
├── PIPELINE.md                        run order + dependencies (the map of this repo)
├── run_pipeline.bat                   one-click sequential run of steps [1]–[5] (Windows/conda)
├── .zenodo.json / ZENODO_DESCRIPTION.md   metadata for the Zenodo data deposit
│
├── 0_shape_files/                     shared GIS boundaries (data-only, not tracked)
│   ├── 1_World_Countries/             country polygons
│   ├── 2_LME shape files/             LME sub-segments (cLME_ss_full)
│   ├── 3_BasinID_shape_PCR2/          PCR-GLOBWB river-basin IDs
│   ├── 5_LME_Country_match/           LME sub-segment ↔ country EEZ shares (validated)
│   ├── 6_EEZ_land_union_v3_202003/    EEZ–land union (SHARED by both air pipelines)
│   └── 0_gridcells_LME_mapped.csv     air-grid cell → LME map (SHARED, tracked)
│
├── A_agricultural_leaching/           waterborne-N cropland & grazing pathway (Python)
│   ├── 1_crop_eutrophication_pipeline.py     crop-disaggregated leaching -> LME
│   ├── 2_grazing_eutrophication_pipeline.py  grazing/pasture twin
│   ├── 2. N_application_rate/a_download_adalibieke.py   TPDC downloader (credentials NOT
│   │                                  included — request your own, see Security note)
│   ├── 3. CFs/b_make_CF_csv_from_tif.py      CF_arable_final.tif -> CF_arable.csv
│   ├── 1. Input_IMAGE_GNM/ · 2. N_application_rate/ · 3. CFs/   raw inputs (data)
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
├── C_airborne_NOx/                    NOₓ twin of B (Python; CF built by CF_NOx.m)
│
├── D_Final_Database/                  the harmonisation layer
│   ├── 0_harmonise_pathways.py        READ-ONLY stack of crop/grazing/NH₃/NOₓ at
│   │                                  pathway × year × country × activity × LME
│   └── eutrophication_all_pathways.parquet   (generated)
│
├── E_MRIO_GLORIA_Satellites/          GLORIA v60 satellite builder (Python)
│   ├── 0_build_MRIO_satellites.py     LINEAR script, steps prep→water→NH3→NOx→verify
│   ├── 0. data_GLORIAv60/             GLORIA_ReadMe_060.xlsx, country→region map,
│   │                                  crop→sector match, GLORIA60 emission vectors
│   │                                  (NH3/, NOx/ — the air disaggregation keys)
│   │                                  + the MATLAB extraction scripts that made them
│   └── 1. GLORIAv60_Eutrophication_Satellites/                 satellite_<flow>_<year>.mat/.npz (305 LME rows ×
│                                      39,360 GLORIA columns, exact sequential order),
│                                      row/column labels, excluded/unmatched tables,
│                                      build_report.txt (generated)
│
└── F_Practical_case/                  MRIO accounts (MATLAB) + case study
    ├── A_1_GLORIA_prepALx_v3_1.m      GLORIA T,Y -> A, L, x, x_cty, Y_cty ('matrix calc')
    ├── D_1/D_2/D_3_Creation_main_database_*.m   production-based accounts (GCSI lineage)
    ├── E_1_Consumption_eutrophication_LME.m     consumption footprints per LME sub-segment
    │                                  + product-level detail for the 7 coral-reef LME-ss
    ├── Thesis report_Niclas_Pannier.pdf         the case-study thesis (LME selection)
    └── results/                       FP matrices + focus tables (generated)
```

Tracked in git: the `.py`/`.m`/`.bat` sources, `PIPELINE.md`, the Zenodo
metadata files, `Wang2025_leaching_factors.csv`, `MouthID_PCR2.csv`,
`0_gridcells_LME_mapped.csv`, and this README. Everything else (raw data,
shapefiles, `.h5`/`.nc`/`.tif`, Parquet/`.mat`/`.npz` outputs) is excluded by
`.gitignore` and lives in the Zenodo archive.

---

## Environment

Python pipelines (steps [1]–[5]): plain NumPy/pandas plus a few geospatial
libraries. A conda-forge environment:

```bash
conda create -n geo2 -c conda-forge python=3.11 \
    numpy pandas scipy xarray netCDF4 h5netcdf h5py \
    geopandas shapely pyproj rasterio pyarrow openpyxl
conda activate geo2
```

(`run_pipeline.bat` activates an env named `geo2`; rename inside the .bat if
yours differs. `a_download_adalibieke.py` needs only the standard library.)

MATLAB (step [6], folder F): R2021a or newer; ~64 GB RAM recommended when the
dense GLORIA Leontief inverse `L` (~12 GB) is loaded for the product-level
detail. The aggregate consumption matrices run without `L`.

Every script runs **either** whole (`python <script>.py` / F5) **or**
cell-by-cell (`# %%` / `%%` cells), with plain inspectable variables — the code
is deliberately linear with as few functions as possible, so it can be reviewed
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
   emissions by the atmospheric source→receptor CF matrix (2° grid), map
   receptors to LME sub-segments, and aggregate by emitting country × IPCC
   sector × LME; also emit cell-level databases, receptor-country tables,
   per-cell maps and CF layers (see `3. Output/_README.txt`).
4. **[4] `D_…/0_harmonise_pathways.py`** — stacks all four pathways into
   `eutrophication_all_pathways.parquet`
   (`pathway | substance | year | emission_country | activity_type | activity |
   LME_nb_f_1 | release_kg | release_kgN | CF_kgO2_per_kg | eutrophication_kgO2`).
5. **[5] `E_…/0_build_MRIO_satellites.py`** — builds, per year × flow
   (N-leach, NH₃, NOₓ), a sparse **305 × 39,360** satellite in the exact GLORIA
   v60 sequential column order (values on industry columns), as `.mat` + `.npz`.
   Agriculture maps ~1:1 to GLORIA crop/cattle sectors; air sectors are split
   with GLORIA's own per-label emission vectors as region-specific keys. The
   `verify` step must print `OK` on every flow × year line
   (`1. GLORIAv60_Eutrophication_Satellites/build_report.txt`).
6. **[6] `F_…` (MATLAB)** — run `A_1_GLORIA_prepALx_v3_1.m` once per year
   (set `gloria_vrs = 60`, years 2015–2022; needs the GLORIA release on a local
   drive) to create `L, x, x_cty, Y_cty`, then
   **`E_1_Consumption_eutrophication_LME.m`**: computes
   `FP = (S./x') · x_cty` → **305 LME-ss × 164 consuming regions** per flow ×
   year, checks that consumption totals reproduce each LME's production total,
   and, for the seven coral-reef LME sub-segments of the Pannier case study
   (12_1, 12_2, 10, 40_4, 36_18, 49, 36_13), resolves the footprint into
   individual final products × supplying region × consuming region
   (`B_r = q̂L`, `D = B_rᵀ ∘ Y_cty`).

Re-running an upstream step invalidates everything below it — resume from there.

---

## Method (short)

For each 0.5° IMAGE-GNM grid box the cropland N-leaching flow `L_box` is split
across the 5-arcmin cells and crops inside it by a leaching-potential weight
`P = Nsyn·LF_crop + Nman·LF_organic`, so `L(cell,crop) = L_box · P / ΣP`;
marine eutrophication is `E = L · 10⁹ · CF(cell)` with the waterborne-N
characterisation factor routed basin → river mouth → LME. Atmospheric
deposition is **removed** from the IMAGE surplus so the cropland pathway does
not double-count the airborne streams: NH₃ and NOₓ are treated separately by
applying a source→receptor atmospheric fate matrix (2° grid) to EDGAR v8.1
emissions and aggregating receptors to LME sub-segments. The harmonised
database expresses all releases both in native mass and as kg N (NH₃ ×14/17,
NOₓ ×14/46 as NO₂). The satellites place each (country, activity, LME) impact
on GLORIA v60 industry columns, and the MATLAB step allocates it to final
demand with a standard Leontief demand-pull model. All impacts in **kg O₂-eq**.

## Modelling choices flagged `REVIEW` in the code

- **Receptor-country tables (DB2 / `3_receptor_countries`)** split each LME's
  impact over the countries whose EEZ composes it by validated area shares —
  this assumes impact spread uniformly within the LME. The satellites and all
  MRIO results use only the producer-side (DB1) chain.
- **NOₓ 3C1b (agricultural waste burning)**: GLORIA's own NOₓ 3C1b vector is
  zero in every year, so the split key is borrowed from NH₃ 3C1 — the same
  physical activity (`EMPTY_LABEL_PROXY` in the satellite builder; every use
  is printed and counted).
- **High seas (ABNJ) and the Antarctic EEZ** are excluded from the satellites —
  GLORIA has no international-transport or Antarctica region — and quantified
  in `satellite_excluded_<flow>.csv`.
- The legacy NOₓ aviation label typo (`1A31a`) is corrected to `1A3a`
  throughout; `CF_kgO2_per_kg` in the harmonised table is an *effective*
  (result-side) ratio, not an intrinsic fate factor.

---

## Data availability

None of the large datasets are redistributed via GitHub; obtain each from its
source, or take the exact versions used from the Zenodo deposit
(**DOI: to be added** — `ZENODO_DESCRIPTION.md` documents the archive).
Identifiers marked *(confirm)* should be completed before release.

| Dataset | Used for | Source |
|---|---|---|
| Adalibieke crop-specific N fertilisation (+ harvested area), `*.h5` | crop weights `Nsyn/Nman` | TPDC, `https://data.tpdc.ac.cn` — personal FTP credentials required, see `a_download_adalibieke.py` *(confirm dataset DOI)* |
| IMAGE-GNM cropland N budget (SSP2), `…CroplandBudget-v2.nc` | leaching magnitude `L_box` | IMAGE-GNM, PBL Netherlands Environmental Assessment Agency *(confirm citation)* |
| CF_arable (5-arcmin waterborne-N CF), `CF_arable_final.tif` | `CF(cell)` | Vea et al. 2022 *(confirm DOI)* |
| N leaching factors, `Wang2025_leaching_factors.csv` | `LF_crop`, `LF_organic` | Wang et al. 2025 *(confirm citation)* — **in repo** |
| EDGAR v8.1 NH₃ / NOₓ gridded emissions | airborne source terms | EDGAR, EU JRC, `https://edgar.jrc.ec.europa.eu` (CC-BY 4.0) |
| Atmospheric source→receptor CF matrices, `CF_NHx_all.csv`, `CF_NOx_all.csv` | airborne fate | generated (NOₓ builder: `CF_NOx.m`; Cosme & Hauschild-based marine effect) *(document version)* |
| LME sub-segments, `cLME_ss_full.shp` | receptor aggregation | LME boundaries, custom sub-segment version *(confirm source)* |
| EEZ / country polygons, EEZ–land union v3 (2020-03) | country tagging | Marine Regions, `https://marineregions.org` |
| River-basin IDs, `BasinID_PCR2.shp`, `MouthID_PCR2.csv` | basin → mouth → LME | PCR-GLOBWB ("PCR2") *(confirm)* — mouth table **in repo** |
| GLORIA v60 MRIO (T, Y, satellites, ReadMe) | folders E + F | University of Sydney IELab GLORIA release — **not redistributed**; register with IELab *(confirm exact release/citation)* |
| Pannier, N. — thesis report (case-study LME selection) | folder F focus LMEs | included in `F_Practical_case/` |

---

## Security note

`a_download_adalibieke.py` ships with **placeholder credentials only** and
refuses to run until you insert your own (or set `TPDC_USER` / `TPDC_PASS`):
TPDC issues personal FTP credentials per data request. Never commit real
credentials; if any were committed in an earlier private history, rotate them
(request fresh TPDC access) before making the repository public.

## License & citation

Released under **CC-BY 4.0** (add the `LICENSE` file); third-party datasets
remain under their original terms (table above). If you use this code or the
deposited data, cite the paper (reference at the top) and the Zenodo record
(DOI: *to be added*).

## Contact

Etienne Berthet — Massachusetts Institute of Technology
*(add preferred contact e-mail / ORCID before release)*
