# Zenodo record — metadata + description (full archive)

Everything to paste into the Zenodo upload form (https://zenodo.org/uploads/new).
The machine-readable twin is `.zenodo.json` (same content; used automatically if
the GitHub repo is ever linked to Zenodo).

**Framing:** this is a **standalone methods-and-data deposit** — it describes the
model chain and the models it builds on (Cosme & Hauschild; Vea et al.;
IMAGE-GNM/Beusen; EDGAR/Crippa; Adalibieke; GLORIA), and does **not** reference
the journal article. If you later want to connect the published article, add it
under *Edit → Related works* — record metadata stays editable after publication;
only the files are frozen (new files = new version).

**Remaining TODOs:** add each author's ORCID in the form (recommended, not
required) · confirm the co-authors agree to be listed as creators of the data
record · bump `version` on any re-upload.

---

## Form fields

| Field | Value |
|---|---|
| Upload type | Dataset |
| Title | Coastal marine eutrophication footprint of reactive nitrogen: global emission-to-impact model chain and GLORIA MRIO satellites (2015–2022) |
| Creators | Berthet, Etienne (MIT Center for Sustainability Science and Strategy, MIT) · Vea, Eldbjørg B. (DTU) · Panier, Nicolas (DTU) · Morris, Jennifer (MIT CS3) · Laurent, Alexis (DTU) — add ORCIDs |
| License | Creative Commons Attribution 4.0 (CC-BY-4.0) |
| Language | English |
| Version | 1.0.0 |
| Keywords | marine eutrophication; reactive nitrogen; nitrogen footprint; coastal eutrophication; Large Marine Ecosystems; life cycle impact assessment; characterisation factors; multi-regional input–output analysis; GLORIA MRIO; EDGAR; IMAGE-GNM; consumption-based accounting; ammonia; nitrogen oxides; nitrogen leaching; coral reefs |
| Related works | `is derived from` → doi:10.11888/Terre.tpdc.300446 (TPDC fertilisation dataset); `cites` → the model DOIs in the References section below. *(No journal-article link — add later if wanted.)* |
| References | paste the reference list below |

---

## Description (paste into the Description field)

Global model chain and dataset quantifying the **coastal marine eutrophication
footprint of reactive nitrogen (2015–2022)** — from nitrogen emissions, through
spatially explicit fate and effect modelling, to the final consumption
ultimately driving the impacts.

Three pathways are covered: **agricultural leaching** of waterborne N,
**airborne NH₃**, and **airborne NOₓ**. Impacts are expressed in **kg O₂-eq**
(marine oxygen depletion) and resolved to **305 coastal Large Marine Ecosystem
sub-segments (cLME-ss)**, carrying the emitting country and the driving
activity (crops, grazing, IPCC sectors). The three pathways are harmonised into
one comparable database, converted into **GLORIA v60 MRIO satellite matrices**
(305 LME-ss rows × 39,360 region–sector columns, per year and substance), and
traced to final demand with a Leontief demand-pull model — including
product-level detail for seven coral-reef LME sub-segments.

**Underlying models and data.** The framework builds on and couples:

- the spatially differentiated marine-eutrophication assessment models of
  **Cosme & Hauschild (2017)**, **Cosme, Mayorga & Hauschild (2018)** and
  **Vea et al. (2022, 2024)**, with atmospheric characterisation following
  **Bjørn et al. (2020)**;
- the **IMAGE-GNM** global nutrient model (**Beusen et al., 2015; Beusen &
  Bouwman, 2022**) for soil nitrogen budgets;
- **EDGAR v8.1** gridded NH₃/NOₓ emissions (**Crippa et al., 2024**);
- the crop-specific nitrogen fertilisation dataset of **Adalibieke et al.
  (2023)**;
- the **GLORIA** global environmentally-extended MRIO database, release 060
  (University of Sydney IELab; cf. **Lenzen et al., 2013; Malik et al., 2022**).

**Contents.** Shared GIS layers and grid–LME correspondences (folder 0); the
crop and grazing leaching pipelines (A); the NH₃/NOₓ emission preparation and
impact pipelines, including the characterisation-matrix builders `CF_NHx.m` /
`CF_NOx.m` (B, C); the harmonised all-pathway database in Parquet (D); the
GLORIA v60 satellite builder with row/column labels, exclusion tables and a
conservation report (E); and the MATLAB MRIO scripts for production- and
consumption-based accounts with the coral-reef case study (F). Every pipeline
is a single linear, cell-structured script with built-in conservation checks;
`PIPELINE.md` documents the execution order and `run_pipeline.bat` runs the
whole chain. Modelling choices a reviewer should see are flagged `REVIEW` in
the scripts and reports (receptor-country attribution assumption, the NOₓ 3C1b
proxy split key, high-seas/Antarctica exclusions).

**Units & conventions.** Impacts: kg O₂-eq. Emissions: kg NH₃, kg NOₓ (as
NO₂), kg N (leaching), with all releases also normalised to kg N (NH₃ ×14/17,
NOₓ ×14/46). Grids: agriculture 5 arcmin, EDGAR 0.1°, atmospheric fate 2°;
receptors: cLME-ss labels `<LME>_<sub-segment>`.

**Environment.** Python ≥3.10 (pandas, geopandas, numpy, scipy, xarray, h5py,
rasterio, pyarrow, openpyxl); MATLAB R2021a+ for folder F.

**Not redistributed** — with pointer files inside the archive
(`_DATA_NOT_INCLUDED_README.txt`) explaining exactly how to obtain each:

- the TPDC crop-specific fertilisation HDF5 files (personal download
  credentials; doi:10.11888/Terre.tpdc.300446) — folder `2. N_application_rate`;
- the IMAGE-GNM budget netCDFs (INMS data portal, registered users) — folder
  `1. Input_IMAGE_GNM`;
- the GLORIA core matrices (T, Y, satellite accounts; IELab registration).

Third-party data remain under their original licenses and citation
requirements; cite the original sources when reusing them.

---

## References (paste into the References field)

- Cosme, N., & Hauschild, M. Z. (2017). Characterization of waterborne nitrogen emissions for marine eutrophication modelling in life cycle impact assessment at the damage level and global scale. *The International Journal of Life Cycle Assessment*, 22(10), 1558–1570. https://doi.org/10.1007/s11367-017-1271-5
- Cosme, N., Mayorga, E., & Hauschild, M. Z. (2018). Spatially explicit fate factors of waterborne nitrogen emissions at the global scale. *The International Journal of Life Cycle Assessment*, 23(6), 1286–1296. https://doi.org/10.1007/s11367-017-1349-0
- Vea, E. B., Bendtsen, J., Richardson, K., Ryberg, M., & Hauschild, M. (2022). Spatially differentiated marine eutrophication method for absolute environmental sustainability assessments. *Science of The Total Environment*, 843, 156873. https://doi.org/10.1016/j.scitotenv.2022.156873
- Vea, E. B., Jwaideh, M., Richardson, K., Ryberg, M., Bjørn, A., & Hauschild, M. (2024). Enabling comprehensive assessment of marine eutrophication impacts and their evaluation against regional safe operating space. *The International Journal of Life Cycle Assessment*, 29(9), 1738–1755. https://doi.org/10.1007/s11367-024-02311-z
- Bjørn, A., Sim, S., King, H., Margni, M., Henderson, A. D., Payen, S., & Bulle, C. (2020). A comprehensive planetary boundary-based method for the nitrogen cycle in life cycle assessment. *Science of The Total Environment*, 715, 136813. https://doi.org/10.1016/j.scitotenv.2020.136813
- Beusen, A. H. W., Van Beek, L. P. H., Bouwman, A. F., Mogollón, J. M., & Middelburg, J. J. (2015). Coupling global models for hydrology and nutrient loading to simulate nitrogen and phosphorus retention in surface water — description of IMAGE-GNM and analysis of performance. *Geoscientific Model Development*, 8(12), 4045–4067. https://doi.org/10.5194/gmd-8-4045-2015
- Beusen, A. H. W., & Bouwman, A. F. (2022). Future projections of river nutrient export to the global coastal ocean show persisting nitrogen and phosphorus distortion. *Frontiers in Water*, 4. https://doi.org/10.3389/frwa.2022.893585
- Crippa, M., Guizzardi, D., Pagani, F., et al. (2024). Insights into the spatial distribution of global, national, and subnational greenhouse gas emissions in the Emissions Database for Global Atmospheric Research (EDGAR v8.0). *Earth System Science Data*, 16(6), 2811–2830. https://doi.org/10.5194/essd-16-2811-2024
- Adalibieke, W., Cui, X., Cai, H., You, L., & Zhou, F. (2023). Global crop-specific nitrogen fertilization dataset in 1961–2020. *Scientific Data*, 10, 617. https://doi.org/10.1038/s41597-023-02526-z
- Malik, A., Oita, A., Shaw, E., Li, M., Ninpanit, P., Nandel, V., Lan, J., & Lenzen, M. (2022). Drivers of global nitrogen emissions. *Environmental Research Letters*, 17(1), 015006. https://doi.org/10.1088/1748-9326/ac413c
- Lenzen, M., Moran, D., Kanemoto, K., & Geschke, A. (2013). Building Eora: A global multi-region input–output database at high country and sector resolution. *Economic Systems Research*, 25(1), 20–49. https://doi.org/10.1080/09535314.2013.769938

---

## Pre-upload checklist (full archive)

1. ~~Remove the personal TPDC FTP credentials from `a_download_adalibieke.py`~~ — **done** (placeholders + env-var lookup; refuses to run without personal credentials).
2. ~~Pointer files in the two excluded data folders~~ — **done** (`_DATA_NOT_INCLUDED_README.txt` in `1. Input_IMAGE_GNM` and `2. N_application_rate`).
3. Delete every `_to_delete/` staging folder and `__pycache__/`; drop the `.bak` files.
4. Optional but recommended: exclude the superseded 3 GB legacy CSVs and `0. Old/` folders (the Parquet databases replace them).
5. Re-run `run_pipeline.bat` end-to-end once; `build_report.txt` must show `OK` on every flow × year line with no `satellite_unmatched_*` files left.
6. Zip per top-level folder as **.zip** (create with 7-Zip, `-tzip -mx=1`; exclude the `.h5`/`.nc` per the folder pointer files) — zip previews in the Zenodo browser and opens everywhere; plus `README.md`, `PIPELINE.md`, `.zenodo.json` loose at the record root.
7. Reserve the DOI on the upload form ("Get a DOI now") so it can go into the article's Data Availability statement; fill ORCIDs; then Publish.
