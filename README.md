# Supporting Information — Coastal marine eutrophication footprint of reactive nitrogen

Analysis code and workflow for the Supporting Information of:

> **\<Authors\>, "\<Paper title\>", \<Journal\> (\<year\>). DOI: \<to be added\>**

This repository quantifies the marine eutrophication impact of reactive
nitrogen reaching the ocean through three pathways — **agricultural leaching**
of waterborne N, **airborne NH₃**, and **airborne NOₓ** — resolves it to Large
Marine Ecosystem (LME) sub-segments, and (folder E) allocates it to final
consumption through a **GLORIA multi-regional input–output (MRIO)** model.

> [!IMPORTANT]
> **Data are not stored in this repository.** The full working folder is
> ~28 GB and GitHub rejects any file larger than 100 MB. Only the code and a
> couple of small input tables are tracked here; every large dataset must be
> obtained from its original source or from the archived data deposit (see
> [Data availability](#data-availability)).

---

## Repository layout

```
Supporting_Information/
├── 0_shape_files/                     GIS boundaries (data-only, not tracked)
│   ├── 1_World_Countries/             country + EEZ polygons
│   ├── 2_LME shape files/             LME sub-segments (cLME_ss_full)
│   ├── 3_BasinID_shape_PCR2/          PCR-GLOBWB river-basin IDs
│   ├── 6_EEZ_land_union_v3_202003/    EEZ–land union (SHARED by both air scripts)
│   └── 0_gridcells_LME_mapped.csv     air-grid cell → LME map (SHARED, tracked)
│
├── A_agricultural_leaching/           Waterborne-N cropland & grazing pathway
│   ├── 2. N_application_rate/a_download_adalibieke.py   fetch the Adalibieke data (TPDC FTP)
│   ├── 3. CFs/b_make_CF_csv_from_tif.py                 CF_arable_final.tif -> CF_arable.csv
│   ├── 1_crop_eutrophication_pipeline.py     crop-disaggregated leaching -> LME
│   ├── 2_grazing_eutrophication_pipeline.py  grazing/pasture leaching -> LME
│   ├── 1. Input_IMAGE_GNM/            IMAGE-GNM cropland N budget (.nc, data)
│   ├── 2. N_application_rate/          Adalibieke crop files (.h5, data)
│   ├── 3. CFs/                         CF_arable raster + csv (data)
│   ├── 4. Leaching_factors/            Wang 2025 leaching factors (tracked)
│   ├── 5. outputs_crops/              generated (not tracked)
│   └── 6. outputs_grazing/            generated (not tracked)
│
├── 0_prepare_EDGAR_emissions.py       ONE prep script: raw EDGAR v8.1 txt -> both emission
│                                      databases (Parquet; verified against the legacy CSVs)
│
├── B_airborne_NH3/                    NH₃ emissions × atmospheric CF -> LME
│   ├── apply_NH3_CF_country_LME.py    main script (country × sector × LME)
│   ├── 1. EDGARv8.1_NH3emissions/     raw EDGAR sector txt + extraction script (data)
│   ├── 2. CFs/CF_NHx_all.csv          source→receptor CF matrix (data)
│   ├── 3. Output/                     all NH₃ results (generated)
│   └── NH3_EDGAR_2015_2022.parquet    prepared emission database (generated)
│
├── C_airborne_NOx/                    NOₓ emissions × atmospheric CF -> LME
│   ├── apply_NOx_CF_country_LME.py    main script (country × sector × LME)
│   ├── 1. EDGAR_V8.1_NOx/             raw EDGAR sector txt + extraction script (data)
│   ├── 2. CFs/                        CF_NOx.m (MATLAB builder) + CF_NOx_all.csv (data)
│   ├── 3. Output/                     all NOₓ results (generated)
│   └── NOx_EDGAR_2015_2022.parquet    prepared emission database (generated)
│
├── D_Final_Database/                  FINAL harmonised database
│   ├── 0_harmonise_pathways.py        READ-ONLY stack of crop, grazing, NH₃, NOₓ at
│   │                                  country × activity × LME (release_kg, release_kgN,
│   │                                  effective CF, eutrophication_kgO2)
│   └── eutrophication_all_pathways.parquet   (generated)
│
└── E_MRIO_GLORIA_Sattelites/          MRIO allocation to final consumption
    ├── 1. Nitrogen/                   waterborne-N satellite + results
    ├── 2. NH3/                        NH₃ satellite + results
    └── 3. NOx/                        NOₓ satellite + results
        (built in Alteryx — .yxdb workflows/databases; no Python here)
```

Tracked in git: the `.py` and `.m` source files, `Wang2025_leaching_factors.csv`,
`MouthID_PCR2.csv`, and this README. Everything else (raw data, shapefiles,
`.h5`/`.nc`/`.tif`, Alteryx `.yxdb`, and regenerable output CSVs) is excluded by
`.gitignore`.

---

## Environment

The pipelines are plain NumPy/pandas with a few geospatial libraries. A
conda-forge environment is recommended:

```bash
conda create -n eutro -c conda-forge python=3.11 \
    numpy pandas xarray netCDF4 h5netcdf h5py \
    geopandas shapely pyproj rasterio
conda activate eutro
```

`a_download_adalibieke.py` uses only the Python standard library (`ftplib`), so
it runs without the geospatial stack.

Scripts are written to run **either** whole (`python <script>.py` / F5 in Spyder)
**or** cell-by-cell (the `# %%` cells). When running cell-by-cell, set the
working directory to the script's folder — the main pipelines already fall back
to `os.getcwd()` when `__file__` is undefined.

---

## How to run

### A — Agricultural leaching (Python)

1. **`a_download_adalibieke.py`** (in `2. N_application_rate/`) — downloads the Adalibieke crop-specific
   N-application and harvested-area files into `2. N_application_rate/`. The TPDC
   FTP server is flaky; the script resumes partial files, so just re-run it until
   every file is complete. *(See the security note below before publishing this
   file.)*
2. **`b_make_CF_csv_from_tif.py`** (in `3. CFs/`) — converts the 5-arcmin CF raster
   (`CF_arable_final.tif`, Vea et al. 2022) into `CF_arable.csv`.
3. **`1_crop_eutrophication_pipeline.py`** — splits the IMAGE-GNM cropland N
   surplus into (cell × crop) using the leaching-potential weights, multiplies by
   the CF, and writes `5. outputs_crops/crop_eutrophication_cells_<year>.csv`
   for 2015–2022.
4. **`2_grazing_eutrophication_pipeline.py`** — the grazing/pasture twin, writing
   to `6. outputs_grazing/`.

### B / C — Airborne NH₃ and NOₓ (Python; MATLAB for the NOx CF)

0. **`0_prepare_EDGAR_emissions.py`** (repo root) — builds both emission databases
   from the raw EDGAR v8.1 sector files (`1. EDGAR…` folders) with the exact legacy
   sector labels, writes compact Parquet, and self-verifies against the legacy CSVs.

`apply_NH3_CF_country_LME.py` and `apply_NOx_CF_country_LME.py` multiply gridded
EDGAR emissions (Parquet preferred, CSV fallback) by a precomputed source→receptor
characterization-factor matrix
(`CF_*_all.csv`), map receptors to LME sub-segments, and aggregate the marine
eutrophication impact by emitting **country × IPCC sector × LME**. They also emit
per-cell impact maps and per-LME / per-cell CF layers. `CF_NOx.m` documents how
the NOₓ CF matrix was built.

### E — MRIO / GLORIA (Alteryx)

Folder E contains the input–output allocation to final consumption. It is built
in **Alteryx** (`.yxdb` databases and workflows), not Python, and is included
here as data/workflow provenance.

### D — Final database

`0_harmonise_pathways.py` reads the pathway outputs (A, B, C — nothing is modified)
and stacks them into `eutrophication_all_pathways.parquet`: one row per year ×
pathway × emission country × activity (crop / grazing / IPCC sector) × LME, with
the release in native mass and as kg N, the effective CF, and the eutrophication
in kg O₂. Run it after the A/B/C pipelines.

---

## Method (one paragraph)

For each 0.5° IMAGE-GNM grid box the cropland N-leaching flow `L_box` is split
across the 5-arcmin cells and crops inside it by a leaching-potential weight
`P = Nsyn·LF_crop + Nman·LF_organic`, so `L(cell,crop) = L_box · P / ΣP`.
Marine eutrophication is `E = L · 10⁹ · CF(cell)`, where CF is the waterborne-N
characterization factor. Atmospheric deposition is **removed** from the IMAGE
surplus so the cropland pathway does not double-count the separate airborne NH₃
and NOₓ streams, which are handled in folders B and C by applying an
atmospheric source→receptor CF matrix to EDGAR emissions and aggregating to LME
sub-segments. Folder E then traces these impacts through the GLORIA MRIO to final
consumption.

---

## Data availability

None of the datasets below are redistributed here; obtain each from its source
(and/or deposit the exact versions used on Zenodo and cite the DOI). Identifiers
marked *(confirm)* should be filled in with the exact citation/DOI before
release.

| Dataset | Used for | Source |
|---|---|---|
| Adalibieke crop-specific N fertilization (+ harvested area), `*.h5` | Crop weights `Nsyn/Nman` | National Tibetan Plateau Data Center (TPDC), `https://data.tpdc.ac.cn` — see `a_download_adalibieke.py` *(confirm dataset DOI)* |
| IMAGE-GNM cropland N budget (SSP2), `Output-IMAGE_GNM-…-CroplandBudget-v2.nc` | Leaching magnitude `L_box` | IMAGE-GNM, PBL Netherlands Environmental Assessment Agency *(confirm citation/access)* |
| CF_arable (5-arcmin waterborne-N eutrophication CF), `CF_arable_final.tif` | `CF(cell)` | Vea et al. 2022 *(confirm full citation/DOI)* |
| N leaching factors, `Wang2025_leaching_factors.csv` | `LF_crop`, `LF_organic` | Wang et al. 2025 *(confirm citation)* — **included in repo** |
| EDGAR NH₃ / NOₓ gridded emissions | Airborne source terms | EDGAR, EU Joint Research Centre, `https://edgar.jrc.ec.europa.eu` |
| Atmospheric source→receptor CF matrices, `CF_NHx_all.csv`, `CF_NOx_all.csv` | Airborne `CF` | Generated (NOx builder: `CF_NOx.m`) *(document method/version)* |
| LME sub-segments, `cLME_ss_full.shp` | Receptor aggregation | Large Marine Ecosystems boundaries (custom sub-segment version) *(confirm source)* |
| EEZ / country polygons, `Countries_EEZ_extended.shp`, `EEZ_land_union_v3_202003` | Country tagging | Marine Regions, `https://marineregions.org` (EEZ land union v3, 2020-03) |
| River-basin IDs, `BasinID_PCR2.shp`, `MouthID_PCR2.csv` | Basin → river-mouth → LME | PCR-GLOBWB basins ("PCR2") *(confirm source)* — mouth table **included in repo** |
| GLORIA MRIO | Consumption-based allocation (folder E) | GLORIA global MRIO database *(confirm version/citation)* |

---

## Security note (read before publishing)

`a_download_adalibieke.py` currently contains a **hard-coded TPDC FTP username
and password**. Do **not** push it as-is to a public repository. Before the first
commit, move the credentials out of the script — e.g. read them from an
environment variable or a local `tpdc_login.txt` that `.gitignore` excludes — or
replace them with placeholders and describe in this README how a user registers
for their own TPDC access. If the credentials have already been committed
anywhere, rotate them (request new TPDC access).

---

## License

Code: *(add a license, e.g. MIT or BSD-3-Clause, in a `LICENSE` file)*.
Data: each dataset remains under the license of its original provider; see
[Data availability](#data-availability).

## Contact

*(add corresponding-author name and email)*
