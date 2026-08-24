# 0_build_MRIO_satellites.py
# ---------------------------------------------------------------------------
# BUILD THE GLORIA MRIO SATELLITE MATRICES - all three nitrogen flows, 2015-2022.
#
#   For each year and each flow (Nleach = crop+grazing, NH3, NOx):
#       one matrix of  305 LME sub-segment ROWS  x  39,360 GLORIA COLUMNS
#   Columns follow EXACTLY the GLORIA v60 sequential order (164 regions x 120
#   sectors x industry/product, sheet 'Sequential region-sector labels' of
#   GLORIA_ReadMe_060.xlsx). Values (kg O2-eq eutrophication) are placed on the
#   INDUSTRY columns only - GLORIA is an industry x product system and the
#   satellite attaches to industries; product columns stay zero.  COLUMN ORDER
#   IS SACRED: the MRIO multiplies these rows against GLORIA's T matrix.
#
# STYLE - LINEAR ON PURPOSE (easy to review and debug):
#   No functions, no call stack. Five top-level blocks, each behind a RUN_*
#   switch, executed straight down with plain loops. After a run (or a single
#   Spyder cell) every intermediate object - labels, reg_cols, c2r, vecs, M -
#   is still in the workspace for inspection.
#
# INPUT  (all read-only)
#   ..\D_Final_Database\eutrophication_all_pathways.parquet   <- run 0_harmonise_pathways.py first
#   0. data_GLORIAv60\GLORIA_ReadMe_060.xlsx                  column order + sector names
#   0. data_GLORIAv60\country_to_GLORIA_region.csv            country -> region acronym
#   0. data_GLORIAv60\NH3|NOx\GLORIA_<yr>_60_<sub>#<label>.csv  GLORIA's own emissions per
#                                                             label (39,360 values) -> the
#                                                             DISAGGREGATION KEY for air
#   0. data_GLORIAv60\FAO_Earthstat_crop_match_GLORIA.xlsx    crop -> GLORIA sector number
#   ..\0_shape_files\5_LME_Country_match\LME_country_match.csv  the 305 LME row order
#
# METHOD
#   Agriculture (crop, grazing): near 1:1. Each (country, crop, LME) impact goes to
#     the (region, crop-sector) industry column. Grazing goes to the 'Raising of
#     cattle' sector (auto-found by name; pin it via GRAZING_SPLIT if needed).
#   Air (NH3, NOx): an IPCC label must be SPLIT across GLORIA sectors. The key:
#     GLORIA's own emission vector for that label & year, restricted to the
#     emitter's region block (industry cols), normalised to 1. Fallback chain,
#     per (label, region): region block -> GLOBAL sector shares of the label
#     (counted + printed) -> proxy label (below) -> unmatched (reported).
#   REVIEW - NOx '3C1b' proxy key: GLORIA60's own NOx vector for 3C1b
#     (agricultural waste burning) is ZERO in every year 2015-2022 (checked),
#     which left ~1.1%/yr of NOx eutrophication unplaced. Same physical activity,
#     other substance: NH3 '3C1' IS populated, so its year-specific vector is
#     used as the split key (EMPTY_LABEL_PROXY). Every use is printed.
#   OUT OF GLORIA SCOPE (excluded + quantified, NOT unmatched):
#     - High seas (ABNJ): the Regions sheet has no international/bunker region and
#       GLORIA's shipping rows hold only ~0.2-0.3x of EDGAR's full 1A3d, so
#       high-seas impacts have no home in a region x sector satellite.
#     - Antarctica: country_to_GLORIA_region.csv maps it to 'Antarctica', which is
#       not a GLORIA region (Antarctic-EEZ shipping, ~0.001% of NOx).
#
# OUTPUT  (in "1. GLORIAv60_Eutrophication_Satellites\")
#   satellite_<flow>_<year>.mat     MATLAB: sparse 'S' (305 x 39360) + row labels
#   satellite_<flow>_<year>.npz     the same matrix for Python (scipy.sparse)
#   satellite_row_labels.csv        the 305 LME sub-segments, in row order
#   satellite_column_labels.csv     the 39,360 GLORIA columns, in column order
#   satellite_excluded_<flow>.csv   out-of-scope impacts (ABNJ, Antarctica)
#   satellite_unmatched_<flow>.csv  real mapping failures - a clean run leaves NONE
#                                   (the file is deleted when there is nothing to report)
#   build_report.txt                conservation accounting, rewritten by verify
#   Side files are REWRITTEN on every run of their block (the previous version
#   appended forever, so old rows survived reruns).
#
# HOW TO RUN
#   everything:   python 0_build_MRIO_satellites.py
#   some steps:   python 0_build_MRIO_satellites.py NOx verify
#   Spyder:       set the RUN_* switches below, then run the "# %%" cells top-down
#   Order: prep -> water -> NH3 -> NOx -> verify. Every block reloads what it
#   needs from the prep cache, so any subset can be relaunched once prep has run.
# Env: pandas numpy scipy openpyxl (+ pyarrow for the parquet input)
# ---------------------------------------------------------------------------

# %% 0) RUN switches + configuration
import os
import re
import sys
import glob
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.io import savemat

RUN_PREP   = True     # parse GLORIA ReadMe + rebuild every lookup (cached, cheap)
RUN_WATER  = True     # crop + grazing  -> satellite_Nleach_<year>
RUN_NH3    = True     # airborne NH3    -> satellite_NH3_<year>
RUN_NOX    = True     # airborne NOx    -> satellite_NOx_<year>
RUN_VERIFY = True     # conservation accounting -> build_report.txt

# command-line override, e.g.:  python 0_build_MRIO_satellites.py NOx verify
# (kernel arguments like '-f ...json' are ignored so Spyder/IPython stay unaffected)
_cli = [a.lower() for a in sys.argv[1:] if not a.startswith("-") and not a.endswith(".json")]
if _cli:
    _bad = sorted(set(_cli) - {"prep", "water", "nleach", "nh3", "nox", "verify"})
    if _bad:
        raise SystemExit("unknown step(s) %s - choose from: prep water NH3 NOx verify" % _bad)
    RUN_PREP   = "prep" in _cli
    RUN_WATER  = "water" in _cli or "nleach" in _cli
    RUN_NH3    = "nh3" in _cli
    RUN_NOX    = "nox" in _cli
    RUN_VERIFY = "verify" in _cli

try:
    HERE = os.path.dirname(os.path.abspath(__file__))       # ...\E_MRIO_GLORIA_Sattelites
except NameError:                                           # cell-by-cell in Spyder
    HERE = os.getcwd()
ROOT   = os.path.dirname(HERE)                              # ...\Supporting_Information
G60    = os.path.join(HERE, "0. data_GLORIAv60")
OUTDIR = os.path.join(HERE, "1. GLORIAv60_Eutrophication_Satellites")
os.makedirs(OUTDIR, exist_ok=True)

HARMONISED = os.path.join(ROOT, "D_Final_Database", "eutrophication_all_pathways.parquet")
READYME    = os.path.join(G60, "GLORIA_ReadMe_060.xlsx")
CTRY_MAP   = os.path.join(G60, "country_to_GLORIA_region.csv")
LME_MATCH  = os.path.join(ROOT, "0_shape_files", "5_LME_Country_match", "LME_country_match.csv")
CROP_XLSX  = next((p for p in [
    os.path.join(G60, "FAO_Earthstat_crop_match_GLORIA.xlsx"),
    os.path.join(HERE, "1. Nitrogen", "FAOSTAT", "FAO_Earthstat_crop_match_GLORIA.xlsx")]
    if os.path.exists(p)), os.path.join(G60, "FAO_Earthstat_crop_match_GLORIA.xlsx"))

YEARS = list(range(2015, 2023))
ABNJ  = "High seas (ABNJ)"
NCOLS = 39360

# crops missing from the xlsx match -> GLORIA sector number (REVIEW: the prep block
# prints every crop -> sector assignment with the sector NAME so you can eyeball it)
CROP_EXTRA = {"Rye": 3, "Sweetpotato": 6, "Vegetables": 6, "Others crops": 10, "Fruits": 12}

# grazing -> {sector_number: share}. Empty = prep finds the sector(s) named
# '...cattle...' (GLORIA v60 has exactly one: 16 'Raising of cattle') and prints it.
GRAZING_SPLIT = {}

# our air labels -> the GLORIA60 file slugs, where the two spellings differ
SLUG_ALIAS = {"NOx": {"1A1b_1A1ci_1A1cii_1B1_1B2": "1A1b_1A1c_1B1_1B2"}, "NH3": {}}

# REVIEW - proxy split keys for labels whose OWN GLORIA60 vector is all-zero:
#   (substance, label) -> (substance, label) to borrow the year-specific vector from.
#   NOx 3C1b = agricultural waste burning; NH3 3C1 is the SAME activity, so its
#   region x sector footprint is the appropriate stand-in (see header).
#   NOx 2A   = mineral industry (NMM: cement, lime, ...): GLORIA60's NOx 2A vector
#   (file stem 'NOx_G5') is zero in every year 2015-2022 as well; NH3 2A - the
#   SAME NMM activity (file stem 'NH3_G4') - IS populated and carries the same
#   non-metallic-minerals sector footprint, so it serves as the split key.
#   (Scan of all GLORIA60 vectors, both substances, all years: these are the
#   ONLY two all-zero labels.)
EMPTY_LABEL_PROXY = {("NOx", "3C1b"): ("NH3", "3C1"),
                     ("NOx", "2A"):   ("NH3", "2A")}

# agriculture (World_Countries) spelling -> country_to_GLORIA_region.csv spelling
AG_NAME_ALIAS = {
    "Somalia": "Federal Republic of Somalia",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "St. Lucia": "Saint Lucia",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "Luxembourg": "Grand Duchy of Luxembourg",
    "Comoros": "Comores",
    "Congo DRC": "Democratic Republic of the Congo",
}

# outputs of the previous script version, superseded by the per-flow files
for _old in ["satellite_unmatched.csv", "satellite_excluded_ABNJ.csv"]:
    if os.path.exists(os.path.join(OUTDIR, _old)):
        os.remove(os.path.join(OUTDIR, _old))
        print("removed legacy '%s' (replaced by per-flow excluded_/unmatched_ files)" % _old)

if (RUN_WATER or RUN_NH3 or RUN_NOX or RUN_VERIFY) and not os.path.exists(HARMONISED):
    raise SystemExit("harmonised parquet not found - run D_Final_Database\\0_harmonise_pathways.py first")

# %% 1) PREP - parse the GLORIA column order + build every lookup (rebuilt or cached)
#   Runs when RUN_PREP is on OR when any cache file is missing; afterwards the
#   lookups are ALWAYS reloaded from the cache, so all later blocks use one code
#   path whether prep just ran or ran in an earlier session.
_PREP_FILES = ["_labels.npz", "satellite_column_labels.csv", "satellite_row_labels.csv",
               "_country_to_region_resolved.csv", "_activity_to_sector.csv"]
_have_cache = all(os.path.exists(os.path.join(OUTDIR, f)) for f in _PREP_FILES)

if RUN_PREP or not _have_cache:
    print("== prep : parsing GLORIA_ReadMe_060.xlsx ==")

    # 1a) the 39,360 sequential labels -> region acronym + industry/product side.
    #     A label reads 'France (FRA) Growing wheat industry'. The acronym in (...)
    #     is matched against the Regions sheet (a label can contain several
    #     brackets - only one is a real acronym); the side is the label's last word.
    seq    = pd.read_excel(READYME, sheet_name="Sequential region-sector labels")
    labels = seq["Sequential_regionSector_labels"].astype(str).tolist()
    assert len(labels) == NCOLS, "expected %d sequential labels, got %d" % (NCOLS, len(labels))
    regions = pd.read_excel(READYME, sheet_name="Regions")
    acr_set = set(regions["Region_acronyms"].astype(str))
    acr_re  = re.compile(r"\(([A-Za-z]{2,5})\)")
    reg_of, kind_of = [], []
    for lab in labels:
        acr = next((a for a in acr_re.findall(lab) if a in acr_set), None)
        if acr is None:
            raise ValueError("no region acronym recognised in label: " + lab)
        reg_of.append(acr)
        kind_of.append("industry" if lab.rstrip().endswith("industry") else
                       ("product" if lab.rstrip().endswith("product") else "other"))
    reg_of, kind_of = np.array(reg_of), np.array(kind_of)
    print("   %d industry / %d product columns, %d regions"
          % ((kind_of == "industry").sum(), (kind_of == "product").sum(), len(set(reg_of))))

    # 1b) per region: its 120 industry column indices IN ORDER. Inside a region
    #     block the industry order IS the GLORIA sector order 1..120, so the
    #     absolute column of sector s is  ind_cols[region][s - 1].
    ind_cols = {}
    for r in acr_set:
        ind_cols[r] = np.nonzero((reg_of == r) & (kind_of == "industry"))[0]
        assert len(ind_cols[r]) == 120, "region %s: %d industry cols (expected 120)" % (r, len(ind_cols[r]))
    np.savez_compressed(os.path.join(OUTDIR, "_labels.npz"),
                        reg_of=reg_of, kind_of=kind_of, regions=np.array(sorted(acr_set)),
                        **{("cols_" + r): v for r, v in ind_cols.items()})
    pd.DataFrame({"col_index_1based": np.arange(1, NCOLS + 1), "label": labels,
                  "region": reg_of, "type": kind_of}
                 ).to_csv(os.path.join(OUTDIR, "satellite_column_labels.csv"), index=False)

    # 1c) the 120 sector NAMES (only for the printed crop/grazing review below).
    #     The Sectors sheet lists extra rows under the 120 -> slice hard.
    sect = pd.read_excel(READYME, sheet_name="Sectors")
    _scol = [c for c in sect.columns if "name" in str(c).lower()][0]
    sector_names = sect[_scol].astype(str).tolist()[:120]

    # 1d) LME ROW ORDER: every sub-segment of LME_country_match.csv, sorted
    #     NUMERICALLY on 'lme_segment' (1_1, 1_2, ..., 2_1 ... - a plain string
    #     sort would put 10_1 before 2_1).
    _lme = pd.Series(pd.read_csv(LME_MATCH)["LME_subsegment"].astype(str).unique())
    _p   = _lme.str.split("_", n=1, expand=True)
    if _p.shape[1] == 1:
        _p[1] = "0"
    rows_order = (pd.DataFrame({"L": _lme, "a": _p[0].astype(int),
                                "b": _p[1].fillna("0").astype(int)})
                  .sort_values(["a", "b"])["L"].tolist())
    pd.DataFrame({"row_index_1based": np.arange(1, len(rows_order) + 1),
                  "LME_nb_f_1": rows_order}
                 ).to_csv(os.path.join(OUTDIR, "satellite_row_labels.csv"), index=False)
    print("   LME rows: %d (order saved to satellite_row_labels.csv)" % len(rows_order))

    # 1e) country name -> GLORIA region acronym. The canonical csv wins; then the
    #     agriculture spellings (AG_NAME_ALIAS: 'Luxembourg' -> 'Grand Duchy of
    #     Luxembourg', 'St. Kitts...' -> 'Saint Kitts...', ...); then every name is
    #     also reachable without a trailing '(...)' part. setdefault = never override.
    _cm = pd.read_csv(CTRY_MAP)
    c2r_build = dict(zip(_cm["Country"].astype(str), _cm["Code"].astype(str)))
    for _wc, _mp in AG_NAME_ALIAS.items():
        if _mp in c2r_build:
            c2r_build.setdefault(_wc, c2r_build[_mp])
    for _k in list(c2r_build):
        c2r_build.setdefault(re.sub(r"\s*\([^)]*\)\s*$", "", _k), c2r_build[_k])
    pd.Series(c2r_build).rename("Code").rename_axis("Country").to_csv(
        os.path.join(OUTDIR, "_country_to_region_resolved.csv"))
    print("   country map: %d names resolvable" % len(c2r_build))

    # 1f) crop -> GLORIA sector number (xlsx match wins, CROP_EXTRA fills gaps),
    #     grazing -> cattle sector. EVERY assignment is printed for review.
    _cx = pd.read_excel(CROP_XLSX)
    crop_map = dict(zip(_cx["Earthstat"].astype(str), _cx["GLORIA"].astype(int)))
    for _k, _v in CROP_EXTRA.items():
        crop_map.setdefault(_k, _v)
    print("   crop -> GLORIA sector (REVIEW):")
    for _c in sorted(crop_map):
        _s = crop_map[_c]
        print("     %-14s -> %3d  %s" % (_c, _s, sector_names[_s - 1] if 0 < _s <= 120 else "??"))
    _cattle = [i + 1 for i, nm in enumerate(sector_names) if "cattle" in nm.lower()]
    gsplit  = GRAZING_SPLIT or {s: 1.0 / len(_cattle) for s in _cattle}
    for _s, _w in gsplit.items():
        print("     %-14s -> %3d  %s  (share %.2f)" % ("grazing", _s, sector_names[_s - 1], _w))
    pd.DataFrame({"activity": list(crop_map) + ["grazing"] * len(gsplit),
                  "GLORIA_sector": list(crop_map.values()) + list(gsplit),
                  "share": [1.0] * len(crop_map) + list(gsplit.values())}
                 ).to_csv(os.path.join(OUTDIR, "_activity_to_sector.csv"), index=False)
    print("   prep done -> caches + label files in '1. GLORIAv60_Eutrophication_Satellites'")

# ---- reload the lookups from the cache (single code path for all later blocks) ----
_z        = np.load(os.path.join(OUTDIR, "_labels.npz"), allow_pickle=True)
reg_cols  = {str(r): _z["cols_" + str(r)] for r in _z["regions"]}   # region -> its 120 industry cols
rows_list = pd.read_csv(os.path.join(OUTDIR, "satellite_row_labels.csv")
                        )["LME_nb_f_1"].astype(str).tolist()
row_ix    = {l: i for i, l in enumerate(rows_list)}                 # LME sub-segment -> row 0..304
c2r       = pd.read_csv(os.path.join(OUTDIR, "_country_to_region_resolved.csv"),
                        index_col=0)["Code"].to_dict()              # country name -> region acronym
_act = pd.read_csv(os.path.join(OUTDIR, "_activity_to_sector.csv"))
a2s  = {}                                                           # activity -> [(sector, share)]
for _i, _r in _act.iterrows():
    a2s.setdefault(str(_r["activity"]), []).append((int(_r["GLORIA_sector"]), float(_r["share"])))

# %% 2) WATER - crop + grazing -> one 'Nleach' satellite per year (direct sector map)
#   Placement is near 1:1: the (country, crop, LME) impact goes to the industry
#   column of that country's region and that crop's GLORIA sector - no split key.
if RUN_WATER:
    print("== water (crop + grazing -> Nleach) ==")
    H = pd.read_parquet(HARMONISED, columns=["pathway", "year", "emission_country",
                                             "activity", "LME_nb_f_1", "eutrophication_kgO2"])
    H = H[H["pathway"].isin(["crop", "grazing"])].copy()
    H["activity"]   = np.where(H["pathway"] == "grazing", "grazing", H["activity"])
    H["LME_nb_f_1"] = H["LME_nb_f_1"].astype(str)

    water_unmatched, water_excluded, water_report = [], [], []
    for Y in YEARS:
        d = H[H["year"] == Y]
        if d.empty:
            print("   %d : nothing in the harmonised table - skipped" % Y)
            continue

        # -- sort every row: placeable / EXCLUDED (no GLORIA region) / UNMATCHED.
        #    'code' is the mapped region acronym; NaN when the name is unknown.
        code   = d["emission_country"].map(c2r)
        m_name = code.isna()                                # name not in the country map
        m_reg  = ~m_name & ~code.isin(set(reg_cols))        # mapped, but not a GLORIA region
        m_act  = ~d["activity"].isin(set(a2s))              # crop without a GLORIA sector
        m_lme  = ~d["LME_nb_f_1"].isin(set(row_ix))         # LME not among the 305 rows
        exc_mask = m_reg & ~m_name & ~m_act & ~m_lme        # ONLY issue is the region -> by design
        bad_mask = ~exc_mask & (m_name | m_reg | m_act | m_lme)
        if exc_mask.any():
            _e = d[exc_mask].copy()
            _e["reason"] = ("country maps to '" + code[exc_mask].astype(str)
                            + "' - not a GLORIA region (excluded, like ABNJ)")
            water_excluded.append(_e)
        if bad_mask.any():
            _u = d[bad_mask].copy()
            _rs = pd.Series("", index=_u.index, dtype=object)
            _rs[m_name.reindex(_u.index)] += "country name not in country_to_GLORIA_region.csv; "
            _rs[m_act.reindex(_u.index)]  += "activity has no GLORIA sector; "
            _rs[m_lme.reindex(_u.index)]  += "LME not in satellite_row_labels.csv; "
            _u["reason"] = _rs.str.strip("; ")
            water_unmatched.append(_u)
        ok = d[~(exc_mask | bad_mask)]

        # -- place: dense year matrix, filled group-wise (grouping pre-sums the cells)
        M = np.zeros((len(rows_list), NCOLS))
        for (ctry, actv, lme), grp in ok.groupby(["emission_country", "activity", "LME_nb_f_1"]):
            val  = grp["eutrophication_kgO2"].sum()
            cols = reg_cols[c2r[ctry]]                      # the region's 120 industry columns
            for snum, share in a2s[actv]:                   # 1 sector for crops; split for grazing
                M[row_ix[lme], cols[snum - 1]] += val * share

        # -- save: sparse .npz (Python) + .mat (MATLAB), identical content
        S = sp.csr_matrix(M)
        sp.save_npz(os.path.join(OUTDIR, "satellite_Nleach_%d.npz" % Y), S)
        savemat(os.path.join(OUTDIR, "satellite_Nleach_%d.mat" % Y),
                {"S": S, "LME_rows": np.array(rows_list, dtype=object),
                 "flow": "Nleach", "year": Y, "units": "kg O2-eq"}, do_compression=True)
        line = "Nleach %d : placed %.6e kg O2 in %d nonzero cells" % (Y, S.sum(), S.nnz)
        print("   " + line)
        water_report.append(line)

    # -- side files: REWRITTEN each run; an empty result removes the stale file
    for _frames, _name in [(water_unmatched, "satellite_unmatched_Nleach.csv"),
                           (water_excluded,  "satellite_excluded_Nleach.csv")]:
        _pth = os.path.join(OUTDIR, _name)
        if _frames:
            pd.concat(_frames, ignore_index=True).to_csv(_pth, index=False)
            print("   -> %s (%d rows)" % (_name, sum(len(f) for f in _frames)))
        elif os.path.exists(_pth):
            os.remove(_pth)
    with open(os.path.join(OUTDIR, "_notes_Nleach.txt"), "w") as _fh:
        _fh.write("\n".join(water_report) + "\n")

# %% 3) AIR - NH3 / NOx -> one satellite per year via the GLORIA60 disaggregation key
#   One linear loop runs for NH3, then again for NOx (skipped if its switch is off).
#   Key per (label, region): GLORIA's own emission vector for that label & year on
#   the region's industry columns, normalised to 1. Fallbacks: GLOBAL sector shares
#   of the label when the region block is silent (counted); EMPTY_LABEL_PROXY when
#   the label's whole vector is zero (NOx 3C1b -> NH3 3C1, printed as REVIEW).
for SUB in (["NH3"] if RUN_NH3 else []) + (["NOx"] if RUN_NOX else []):
    print("== %s ==" % SUB)
    H = pd.read_parquet(HARMONISED, columns=["pathway", "year", "emission_country",
                                             "activity", "LME_nb_f_1", "eutrophication_kgO2"])
    H = H[H["pathway"] == SUB].copy()
    H["LME_nb_f_1"] = H["LME_nb_f_1"].astype(str)
    slug_to_ours = {v: k for k, v in SLUG_ALIAS[SUB].items()}   # file slug -> our label

    air_unmatched, air_excluded, air_report = [], [], []
    n_fb_global, n_proxy = 0, 0
    for Y in YEARS:
        d = H[H["year"] == Y]
        if d.empty:
            print("   %d : nothing in the harmonised table - skipped" % Y)
            continue

        # -- GLORIA60 emission vectors of this year, keyed by OUR label spelling
        vecs = {}
        for _f in glob.glob(os.path.join(G60, SUB, "GLORIA_%d_60_%s*#*.csv" % (Y, SUB))):
            _slug = os.path.basename(_f).split("#", 1)[1][:-4]
            vecs[slug_to_ours.get(_slug, _slug)] = np.loadtxt(_f)

        # -- REVIEW: a label with an all-zero own vector borrows the proxy's vector.
        #    The proxy file is located with a WILDCARD stem: the MATLAB extraction
        #    named some files 'GLORIA_<yr>_60_NH3_G4#2A.csv' (group suffix), so an
        #    exact 'NH3#2A' path would miss them.
        for (_ps, _pl), (_qs, _ql) in EMPTY_LABEL_PROXY.items():
            if _ps == SUB and (_pl not in vecs or vecs[_pl].sum() <= 0):
                _pf = sorted(glob.glob(os.path.join(
                    G60, _qs, "GLORIA_%d_60_%s*#%s.csv" % (Y, _qs, _ql))))
                if not _pf:
                    print("   %d : %s '%s' empty AND proxy %s '%s' file missing -> stays unmatched"
                          % (Y, SUB, _pl, _qs, _ql))
                    continue
                vecs[_pl] = np.loadtxt(_pf[0])
                n_proxy += 1
                print("   %d : %s '%s' empty in GLORIA60 -> split key borrowed from %s '%s' (REVIEW)"
                      % (Y, SUB, _pl, _qs, _ql))

        # -- sort rows: ABNJ + no-GLORIA-region -> EXCLUDED; real unknowns -> UNMATCHED
        m_abnj = d["emission_country"] == ABNJ
        code   = d["emission_country"].map(c2r)
        m_name = code.isna() & ~m_abnj                      # name not in the country map
        m_reg  = ~m_abnj & ~m_name & ~code.isin(set(reg_cols))   # mapped, not a GLORIA region
        m_lab  = ~d["activity"].isin(set(vecs))             # label without a GLORIA60 vector
        m_lme  = ~d["LME_nb_f_1"].isin(set(row_ix))         # LME not among the 305 rows
        exc_mask = m_abnj | (m_reg & ~m_name & ~m_lab & ~m_lme)   # ABNJ always by design
        bad_mask = ~exc_mask & (m_name | m_reg | m_lab | m_lme)
        if exc_mask.any():
            _e = d[exc_mask].copy()
            _e["reason"] = np.where(m_abnj[exc_mask],
                                    "high seas (ABNJ) - no GLORIA region by design",
                                    "country maps to '" + code[exc_mask].astype(str)
                                    + "' - not a GLORIA region (Antarctic EEZ)")
            air_excluded.append(_e)
        if bad_mask.any():
            _u = d[bad_mask].copy()
            _rs = pd.Series("", index=_u.index, dtype=object)
            _rs[m_name.reindex(_u.index)] += "country name not in country_to_GLORIA_region.csv; "
            _rs[m_lab.reindex(_u.index)]  += "label has no GLORIA60 vector this year; "
            _rs[m_lme.reindex(_u.index)]  += "LME not in satellite_row_labels.csv; "
            _u["reason"] = _rs.str.strip("; ")
            air_unmatched.append(_u)
        ok = d[~(exc_mask | bad_mask)]

        # -- place: (label, country) fixes the split key, then one row update per LME
        M = np.zeros((len(rows_list), NCOLS))
        glob_share = {}                                     # label -> global 120-sector shares (lazy)
        for (lab, ctry), grp in ok.groupby(["activity", "emission_country"]):
            cols = reg_cols[c2r[ctry]]                      # the region's 120 industry columns
            key  = vecs[lab][cols].astype(float)
            if key.sum() > 0:
                key = key / key.sum()                       # normal case: region's own mix
            else:                                           # region silent for this label ->
                if lab not in glob_share:                   # GLOBAL sector shares as fallback
                    _per = np.zeros(120)
                    for _cc in reg_cols.values():
                        _per += vecs[lab][_cc]
                    glob_share[lab] = _per / _per.sum() if _per.sum() > 0 else None
                if glob_share[lab] is None:                 # vector empty everywhere, no proxy
                    _u = grp.copy()
                    _u["reason"] = "label '%s' empty in GLORIA60 and no proxy defined" % lab
                    air_unmatched.append(_u)
                    continue
                key = glob_share[lab]
                n_fb_global += 1
            for lme, g2 in grp.groupby("LME_nb_f_1"):
                M[row_ix[lme], cols] += g2["eutrophication_kgO2"].sum() * key

        # -- save: sparse .npz (Python) + .mat (MATLAB), identical content
        S = sp.csr_matrix(M)
        sp.save_npz(os.path.join(OUTDIR, "satellite_%s_%d.npz" % (SUB, Y)), S)
        savemat(os.path.join(OUTDIR, "satellite_%s_%d.mat" % (SUB, Y)),
                {"S": S, "LME_rows": np.array(rows_list, dtype=object),
                 "flow": SUB, "year": Y, "units": "kg O2-eq"}, do_compression=True)
        line = "%s %d : placed %.6e kg O2 in %d nonzero cells" % (SUB, Y, S.sum(), S.nnz)
        print("   " + line)
        air_report.append(line)

    air_notes = []
    if n_fb_global:
        air_notes.append("NOTE: %d (label x region x year) splits used the GLOBAL fallback key" % n_fb_global)
    if n_proxy:
        air_notes.append("REVIEW: %d year(s) used a proxy split key (EMPTY_LABEL_PROXY, see header)" % n_proxy)
    for _l in air_notes:
        print("   " + _l)
    air_report += air_notes

    # -- side files: REWRITTEN each run; an empty result removes the stale file
    for _frames, _name in [(air_unmatched, "satellite_unmatched_%s.csv" % SUB),
                           (air_excluded,  "satellite_excluded_%s.csv" % SUB)]:
        _pth = os.path.join(OUTDIR, _name)
        if _frames:
            pd.concat(_frames, ignore_index=True).to_csv(_pth, index=False)
            print("   -> %s (%d rows)" % (_name, sum(len(f) for f in _frames)))
        elif os.path.exists(_pth):
            os.remove(_pth)
    with open(os.path.join(OUTDIR, "_notes_%s.txt" % SUB), "w") as _fh:
        _fh.write("\n".join(air_report) + "\n")

# %% 4) VERIFY - conservation:  source = placed + excluded + unmatched  (per flow x year)
#   source    = the harmonised parquet (what SHOULD be distributed)
#   placed    = the matrix sum (what IS in the satellite)
#   excluded  = ABNJ + Antarctica (documented scope, satellite_excluded_*.csv)
#   unmatched = mapping failures (satellite_unmatched_*.csv) - MUST be 0 for OK
if RUN_VERIFY:
    print("== verify ==")
    Hv = pd.read_parquet(HARMONISED, columns=["pathway", "year", "eutrophication_kgO2"])
    rep = ["build_report.txt - rewritten by the verify step",
           "source = harmonised parquet | placed = matrix sum | excluded = out of GLORIA",
           "scope (ABNJ high seas, Antarctica) | unmatched = mapping failures (must be 0)", ""]
    all_ok = True
    for flow, pws in [("Nleach", ["crop", "grazing"]), ("NH3", ["NH3"]), ("NOx", ["NOx"])]:
        exc_by_year, unm_by_year = {}, {}
        for _name, _dst in [("satellite_excluded_%s.csv" % flow, exc_by_year),
                            ("satellite_unmatched_%s.csv" % flow, unm_by_year)]:
            _pth = os.path.join(OUTDIR, _name)
            if os.path.exists(_pth):
                _t = pd.read_csv(_pth)
                _dst.update(_t.groupby("year")["eutrophication_kgO2"].sum().to_dict())
        for Y in YEARS:
            _f = os.path.join(OUTDIR, "satellite_%s_%d.npz" % (flow, Y))
            if not os.path.exists(_f):
                continue
            placed = sp.load_npz(_f).sum()
            src    = Hv[(Hv["pathway"].isin(pws)) & (Hv["year"] == Y)]["eutrophication_kgO2"].sum()
            exc_y  = exc_by_year.get(Y, 0.0)
            unm_y  = unm_by_year.get(Y, 0.0)
            resid  = src - placed - exc_y - unm_y
            ok     = (abs(resid) <= 1e-6 * max(abs(src), 1.0)) and (unm_y == 0.0)
            all_ok = all_ok and ok
            line = ("%-6s %d : source %.6e = placed %.6e + excluded %.3e + unmatched %.3e"
                    " | resid %+.1e  %s"
                    % (flow, Y, src, placed, exc_y, unm_y, resid,
                       "OK" if ok else "<< CHECK satellite_unmatched_%s.csv" % flow))
            print("   " + line)
            rep.append(line)
        _nt = os.path.join(OUTDIR, "_notes_%s.txt" % flow)
        if os.path.exists(_nt):
            rep += ["", "-- %s build notes --" % flow] + open(_nt).read().strip().split("\n")
    with open(os.path.join(OUTDIR, "build_report.txt"), "w") as _fh:
        _fh.write("\n".join(rep) + "\n")
    print("verify: %s -> build_report.txt" % ("ALL OK" if all_ok else "issues flagged above"))

# %% done
_ran = [n for n, f in [("prep", RUN_PREP), ("water", RUN_WATER), ("NH3", RUN_NH3),
                       ("NOx", RUN_NOX), ("verify", RUN_VERIFY)] if f]
print("DONE:", " -> ".join(_ran) if _ran else "nothing (all RUN_* switches are off)")
