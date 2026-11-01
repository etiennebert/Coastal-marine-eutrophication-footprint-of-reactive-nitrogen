# 2_make_anchored_satellites.py - GLORIA-anchored satellite batch (+ deltas)
# ---------------------------------------------------------------------------
# GLORIA's (EDGAR-consistent) satellite is ACTIVITY-based, not geographic: a
# country's total includes its land emissions AND its own at-sea activities
# (domestic navigation, fishing, offshore platforms in the EEZ). It excludes
# exactly two things: INTERNATIONAL navigation (EDGAR's "SEA" pseudo-country)
# and, in the industry block we anchor to, DIRECT-HOUSEHOLD emissions.
#
# The anchored batch therefore keeps every cell of every sector, and for the
# two sectors where the exclusions live,
#     1A3d        maritime transport  -> international navigation
#     1A3b_noRES  road transport      -> household driving
# rescales each country's impacts by ONE ratio
#     rho_c = min(1, GLORIA_total_c / EDGAR_total_c)
# (uniform over the country's cells - the accepted approximation: the removed
# share carries the sector's average within-country damage intensity).
# By linearity of the CF chain this equals rescaling the gridded emissions,
# so it is done directly on the pair-table impacts - no grid or CF work.
# To also rescale residential (1A4_1A5), add it to FIX below.
#
# The removed excess is saved as per-sector DELTA satellites so the two flows
# stay separable to the Sankeys:   S_anchored + dship + dhh == S  exactly.
#   dship = (1-rho)*1A3d impacts   -> "Int. shipping (at sea)" node in F_4
#   dhh   = (1-rho)*road impacts   -> booked on the country's own diagonal
#
# NEEDS (script stops if missing):
#   <SUB>_impact_country_to_LME.csv        (pair impacts, per country x LME)
#   <SUB>_impact_by_country_sector.csv     (EDGAR totals for the ratio)
# OUTPUT ("1b. GLORIAv60_Eutrophication_Satellites_anchored/"): anchored
# satellite_<SUB>_<Y>.npz/.mat + satellite_{dship,dhh}_<SUB>_<Y>.npz +
# anchored_summary.csv; Nleach + label files copied so E_1 runs unchanged.
# RUN inside E_MRIO_GLORIA_Satellites:  python 2_make_anchored_satellites.py
# Then: E_1 with SAT_DIR -> "1b." folder;  F_4_Sankey_reef.py <year> anchored.
# ---------------------------------------------------------------------------
import glob
import os
import shutil
import sys
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.io import savemat

HERE = os.path.dirname(os.path.abspath(__file__))
G60  = os.path.join(HERE, "0. data_GLORIAv60")
SAT  = os.path.join(HERE, "1. GLORIAv60_Eutrophication_Satellites")
OUTD = os.path.join(HERE, "1b. GLORIAv60_Eutrophication_Satellites_anchored")
os.makedirs(OUTD, exist_ok=True)

YEARS = list(range(2015, 2023))
# Rescaled-to-GLORIA sectors. Options:
#   + "1A4_1A5"  residential/other combustion (household heating; same logic as road)
#   + "1A31a"    aviation - the SAME convention issue exists (international flights
#     over the land-EEZ domain are attributed territorially, ~4% of the NOx
#     pathway), BUT GLORIA's 1A3a vector (25 Tg NO2 in 2015) exceeds all global
#     aviation NOx (~4-5 Tg), so as an anchor it is not credible: rho clips to 1
#     nearly everywhere (no-op) and would misfire where it does not. Leave it out
#     and state the limitation, unless a proper anchor (EDGAR's own domestic-
#     aviation country totals) is wired in.
FIX   = ["1A3d", "1A3b_noRES"]
ALIAS = {"1A3a": "1A31a", "1A1b_1A1c_1B1_1B2": "1A1b_1A1ci_1A1cii_1B1_1B2"}
UF    = 1e6                          # GLORIA vectors are kt -> kg
ABNJ  = "High seas (ABNJ)"
EMISCOL = {"NOx": "emission_kgNO2", "NH3": "emission_kgNH3"}

MODEL = [os.environ.get("EUTRO_MODEL_ROOT", os.path.join(HERE, "..")),   # this model tree first, so a
         r"D:\MIT_Eutrophication_Model"]                                  # stale copy elsewhere is never picked
AIRD  = {"NOx": "C_airborne_NOx", "NH3": "B_airborne_NH3"}
def _find(sub, fname):
    for root in MODEL:
        p = os.path.join(root, AIRD[sub], "3. Output", "1_impact_tables", fname)
        if os.path.exists(p):
            return p
    return None

c2r = pd.read_csv(os.path.join(G60, "country_to_GLORIA_region.csv")) \
        .set_index("Country")["Code"].to_dict()
_z  = np.load(os.path.join(SAT, "_labels.npz"), allow_pickle=True)
reg_cols = {str(r): _z["cols_" + str(r)] for r in _z["regions"]}
rows_lab = pd.read_csv(os.path.join(SAT, "satellite_row_labels.csv"))
ROWCOL   = "LME_nb_f_1" if "LME_nb_f_1" in rows_lab.columns else \
           [c for c in rows_lab.columns if not pd.api.types.is_numeric_dtype(rows_lab[c])][0]
row_ix   = {str(v): i for i, v in enumerate(rows_lab[ROWCOL])}
def _ri(lme):
    """Row index tolerant to the 'X' vs 'X_0' single-segment naming split
    between the satellite row labels (bare) and the air pair tables (suffixed)."""
    s = str(lme)
    ri = row_ix.get(s)
    if ri is None:
        ri = row_ix.get(s + "_0")
    if ri is None and s.endswith("_0"):
        ri = row_ix.get(s[:-2])
    return ri

for f in ["satellite_row_labels.csv", "satellite_column_labels.csv", "_labels.npz"]:
    shutil.copy2(os.path.join(SAT, f), os.path.join(OUTD, f))
for f in glob.glob(os.path.join(SAT, "satellite_Nleach_*.*")):
    shutil.copy2(f, OUTD)

summary = []
for SUB in ["NOx", "NH3"]:
    pair_f = _find(SUB, f"{SUB}_impact_country_to_LME.csv")
    bycs_f = _find(SUB, f"{SUB}_impact_by_country_sector.csv")
    if not (pair_f and bycs_f):
        sys.exit(f"{SUB}: pair or by_country_sector table not found under "
                 + " or ".join(os.path.join(m, AIRD[SUB]) for m in MODEL))
    print(f"{SUB}: pairs <- {pair_f}")
    P = pd.read_csv(pair_f, usecols=["year", "IPCC_sector", "emission_country",
                                     "LME_nb_f_1", "impact_kgO2"])
    P["label"] = P.IPCC_sector.replace(ALIAS)
    P = P[P.label.isin(FIX) & (P.emission_country != ABNJ)]
    B = pd.read_csv(bycs_f).rename(columns={EMISCOL[SUB]: "E"})
    B["label"] = B.IPCC_sector.replace(ALIAS)
    B = B[B.label.isin(FIX)].drop_duplicates(["year", "label", "emission_country"])

    for Y in YEARS:
        satf = os.path.join(SAT, f"satellite_{SUB}_{Y}.npz")
        if not os.path.exists(satf):
            print(f"{SUB} {Y}: satellite missing - skipped"); continue
        S = sp.load_npz(satf).tocsr()

        # GLORIA vectors of the fixed labels, this year (split keys + totals G)
        vec = {}
        for f in glob.glob(os.path.join(G60, SUB, f"GLORIA_{Y}_60_{SUB}*#*.csv")):
            slug = os.path.basename(f).split("#", 1)[1][:-4]
            slug = ALIAS.get(slug, slug)
            if slug in FIX:
                vec[slug] = np.loadtxt(f)
        # GLOBAL sector key per label - the SAME fallback 0_build used when a
        # region's own vector is empty; using anything else (e.g. following the
        # column content) removes mass from columns the label never touched
        gkey = {}
        for lab in FIX:
            if lab in vec:
                per = np.zeros(120)
                for cix in reg_cols.values():
                    per += vec[lab][cix]
                gkey[lab] = per / per.sum() if per.sum() > 0 else None

        # rho(c, s) = min(1, GLORIA / EDGAR); countries without a GLORIA region
        # (or a missing vector) get rho = 0 -> their whole sector is excess
        rho = {}
        for r in B[B.year == Y].itertuples():
            reg = c2r.get(r.emission_country)
            G = float(vec[r.label][reg_cols[reg]].sum()) * UF \
                if (reg in reg_cols and r.label in vec) else 0.0
            rho[(r.emission_country, r.label)] = min(1.0, G / r.E) if r.E > 0 else 0.0

        dship = sp.lil_matrix(S.shape)
        dhh   = sp.lil_matrix(S.shape)
        skipped, lost_lme = {}, {}
        for (lab, ctry), grp in P[P.year == Y].groupby(["label", "emission_country"]):
            excess = 1.0 - rho.get((ctry, lab), 0.0)
            if excess <= 0:
                continue
            reg = c2r.get(ctry)
            if reg is None or reg not in reg_cols:
                skipped[ctry] = skipped.get(ctry, 0) + excess * grp.impact_kgO2.sum()
                continue                      # was never placed in the satellite
            cols = reg_cols[reg]
            key = vec[lab][cols].astype(float) if lab in vec else np.zeros(len(cols))
            tgt = dship if lab == "1A3d" else dhh
            for lme, g2 in grp.groupby("LME_nb_f_1"):
                ri = _ri(lme)
                if ri is None:
                    lost_lme[str(lme)] = lost_lme.get(str(lme), 0) + \
                        excess * g2.impact_kgO2.sum()
                    continue
                k = key.copy()
                if k.sum() > 0:
                    k /= k.sum()
                elif gkey.get(lab) is not None:  # region silent -> GLOBAL key (as in 0_build)
                    k = gkey[lab]
                else:                            # last resort: follow the row's content
                    w = np.asarray(S[ri, cols].todense()).ravel()
                    k = w / w.sum() if w.sum() > 0 else np.full(len(cols), 1 / len(cols))
                d = excess * g2.impact_kgO2.sum()
                tgt[ri, cols] = np.asarray(tgt[ri, cols].todense()).ravel() + d * k

        if skipped:
            top = sorted(skipped.items(), key=lambda kv: -kv[1])[:5]
            print(f"   {SUB} {Y}: not in region map, left unchanged: "
                  + ", ".join(f"{k} ({v:.1e} kg)" for k, v in top))
        if lost_lme:
            print(f"   {SUB} {Y}: ERROR {len(lost_lme)} LME labels matched no satellite "
                  f"row ({sum(lost_lme.values()):.2e} kg dropped) - must be zero: "
                  + ", ".join(list(lost_lme)[:5]))
        dship, dhh = dship.tocsr(), dhh.tocsr()
        Sa = S - dship - dhh
        neg = -Sa.data[Sa.data < 0].sum() if (Sa.data < 0).any() else 0.0
        rel = neg / S.sum()
        # a small residual (~1e-6 of the total) is expected: the pair tables and
        # the harmonised database the satellites were built from are separate
        # runs and not bit-identical; the identity error below IS these clipped
        # elements. Alarm only if it becomes material.
        if rel > 1e-4:
            print(f"   {SUB} {Y}: WARNING clipped {neg:.2e} kg "
                  f"({rel:.1e} of total) - inputs and satellite disagree materially")
        Sa.data = np.maximum(Sa.data, 0.0)
        err = abs((Sa + dship + dhh) - S).max()
        sp.save_npz(os.path.join(OUTD, f"satellite_{SUB}_{Y}.npz"), Sa.tocoo())
        savemat(os.path.join(OUTD, f"satellite_{SUB}_{Y}.mat"),
                {"S": Sa.tocoo(), "LME_rows": np.array(list(rows_lab[ROWCOL]), dtype=object)})
        sp.save_npz(os.path.join(OUTD, f"satellite_dship_{SUB}_{Y}.npz"), dship.tocoo())
        sp.save_npz(os.path.join(OUTD, f"satellite_dhh_{SUB}_{Y}.npz"), dhh.tocoo())
        summary.append(dict(substance=SUB, year=Y, total_Mt=S.sum()/1e9,
                            intl_ship_Mt=dship.sum()/1e9, household_road_Mt=dhh.sum()/1e9,
                            anchored_Mt=Sa.sum()/1e9))
        print(f"{SUB} {Y}: total {S.sum()/1e9:6.2f} | intl shipping {dship.sum()/1e9:5.2f}"
              f" | household road {dhh.sum()/1e9:5.2f} | anchored {Sa.sum()/1e9:6.2f} Mt"
              f"  (residual {err:.1e} kg = {err/S.sum():.1e} of total; = clipped elements)")

pd.DataFrame(summary).to_csv(os.path.join(OUTD, "anchored_summary.csv"), index=False)
print("\nwritten ->", OUTD)
print("next: E_1 with SAT_DIR -> this folder (results to '1. results_anchored'),")
print("      then  python F_4_Sankey_reef.py <year> anchored")
