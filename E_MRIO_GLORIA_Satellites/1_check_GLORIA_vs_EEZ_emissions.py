# 1_check_GLORIA_vs_EEZ_emissions.py
# ---------------------------------------------------------------------------
# How far does OUR emission satellite (EDGAR gridded emissions, attributed to
# the country whose land-EEZ polygon contains each cell) sit from GLORIA v60's
# OWN emission accounts (EDGAR-consistent country totals, which EXCLUDE
# international shipping/aviation - EDGAR books those under the "SEA"/"AIR"
# pseudo-countries, not under any country)?
#
# Part 1 - per pathway (NH3, NOx) x IPCC label x year, at GLORIA-region level:
#     correlation (linear + log10) between our region totals and GLORIA's,
#     global totals + ratio, and the per-region DIFFERENCE for shipping (1A3d):
#     excess = max(ours - GLORIA, 0)  ~ international/transit navigation inside
#     the region's EEZ (GLORIA's country rows ~ domestic navigation), i.e. the
#     share of each country's shipping that no national economy accounts for.
#     -> "transit_share_1A3d.csv" feeds the Sankey reallocation.
# Part 2 - our impact satellite vs GLORIA emissions per GLORIA industry:
#     unit-free comparison of global industry SHARES (impact share vs emission
#     share) - water transport is where the two pictures diverge.
#
# RUN inside E_MRIO_GLORIA_Satellites:  python 1_check_GLORIA_vs_EEZ_emissions.py
# Outputs -> "2. GLORIA_vs_EEZ_check"/ : CSV tables + one scatter PNG per pathway.
# ---------------------------------------------------------------------------
import glob
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
G60  = os.path.join(HERE, "0. data_GLORIAv60")
SAT  = os.path.join(HERE, "1. GLORIAv60_Eutrophication_Satellites")
OUT  = os.path.join(HERE, "2. GLORIA_vs_EEZ_check")
os.makedirs(OUT, exist_ok=True)

# our EDGAR-EEZ emissions per (year, IPCC label, country): the deduplicated
# *_impact_by_country_sector tables. First existing path wins.
MODEL_ROOT = os.environ.get("EUTRO_MODEL_ROOT", os.path.join(HERE, ".."))   # repo tree by default
CAND = {   # this model tree first (or EUTRO_MODEL_ROOT), then the author's D: layout as fallback
  "NOx": [os.path.join(MODEL_ROOT, "C_airborne_NOx", "3. Output", "1_impact_tables", "NOx_impact_by_country_sector.csv"),
          r"D:\MIT_Eutrophication_Model\C_airborne_NOx\3. Output\1_impact_tables\NOx_impact_by_country_sector.csv"],
  "NH3": [os.path.join(MODEL_ROOT, "B_airborne_NH3", "3. Output", "1_impact_tables", "NH3_impact_by_country_sector.csv"),
          r"D:\MIT_Eutrophication_Model\B_airborne_NH3\3. Output\1_impact_tables\NH3_impact_by_country_sector.csv"],
}
EMISCOL = {"NOx": "emission_kgNO2", "NH3": "emission_kgNH3"}
ABNJ    = "High seas (ABNJ)"
YEARS   = list(range(2015, 2023))
# vector-file slug -> our label spelling (same aliases as 0_build_MRIO_satellites)
ALIAS = {"1A3a": "1A31a", "1A1b_1A1c_1B1_1B2": "1A1b_1A1ci_1A1cii_1B1_1B2"}

# --- shared keys: country -> GLORIA region, region -> its 120 industry columns
c2r = pd.read_csv(os.path.join(G60, "country_to_GLORIA_region.csv")) \
        .set_index("Country")["Code"].to_dict()
_z  = np.load(os.path.join(SAT, "_labels.npz"), allow_pickle=True)
reg_cols = {str(r): _z["cols_" + str(r)] for r in _z["regions"]}
collab = pd.read_csv(os.path.join(SAT, "satellite_column_labels.csv"))
collab["sector"] = [l.split(f"({r}) ", 1)[-1].removesuffix(" industry").removesuffix(" product")
                    for l, r in zip(collab["label"], collab["region"])]

# GLORIA books part of road transport / residential combustion under HOUSEHOLD
# final demand, outside the 120 industry columns - for these labels the GLORIA
# industry total is structurally incomplete and the ratio is NOT a gap estimate.
HH_NOTE = {"1A3b_noRES", "1A4_1A5", "1A1b_1A1ci_1A1cii_1B1_1B2"}


def gloria_vec(sub, year, slug_files):
    """label -> 39,360-value GLORIA emission vector (raw units)."""
    out = {}
    for f in slug_files:
        slug = os.path.basename(f).split("#", 1)[1][:-4]
        out[ALIAS.get(slug, slug)] = np.loadtxt(f)
    return out


def corr(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3 or a[m].std() == 0 or b[m].std() == 0:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1])


rows, ship_rows, hh_rows = [], [], []
unit_note = {}
for SUB in ["NOx", "NH3"]:
    src = next((p for p in CAND[SUB] if os.path.exists(p)), None)
    if src is None:
        print(f"{SUB}: no *_impact_by_country_sector.csv found - edit CAND at the top"); continue
    E = pd.read_csv(src).rename(columns={EMISCOL[SUB]: "E", "IPCC_sector": "label"})
    E["label"] = E["label"].replace(ALIAS)                # one canonical spelling on both sides
    E = E.drop_duplicates(["year", "label", "emission_country"])
    E["region"] = E["emission_country"].map(c2r)          # ABNJ / Antarctica -> NaN
    print(f"{SUB}: ours <- {src}")

    for Y in YEARS:
        files = sorted(glob.glob(os.path.join(G60, SUB, f"GLORIA_{Y}_60_{SUB}*#*.csv")))
        if not files:
            continue
        vecs = gloria_vec(SUB, Y, files)
        d = E[E.year == Y]
        abnj_kg = d.loc[d.emission_country == ABNJ, "E"].sum()

        # ---- unit factor for GLORIA vectors, calibrated once on 1A1a (power
        #      plants: purely land-based, both sides are EDGAR -> ratio ~ 1)
        if SUB not in unit_note and "1A1a" in vecs:
            o = d[d.label == "1A1a"].groupby("region")["E"].sum()
            g = pd.Series({r: vecs["1A1a"][cix].sum() for r, cix in reg_cols.items()})
            both = (o > 0) & (g.reindex(o.index).fillna(0) > 0)
            med = float(np.median(o[both] / g.reindex(o.index)[both]))
            unit_note[SUB] = min([1.0, 1e3, 1e6], key=lambda f: abs(np.log10(med / f)))
            print(f"{SUB}: GLORIA vector unit factor -> x{unit_note[SUB]:g} kg "
                  f"(median ours/GLORIA on 1A1a = {med:.3g})")
        UF = unit_note.get(SUB, 1e6)

        # vintage factor: GLORIA v60's satellite is built on an earlier EDGAR
        # release than our v8.1 grids, so even land-only labels sit at a
        # systematic level offset. beta = median ours/GLORIA over well-mixed
        # combustion/industry labels; the ADJUSTED shipping excess removes it.
        _base = []
        for lab in ["1A1a", "1A2", "2B", "2C", "2H", "3A2", "3C", "4C", "1A3c_1A3e", "3C1"]:
            if lab in vecs:
                _o = d[(d.label == lab) & d.region.notna()]["E"].sum()
                _g = sum(vecs[lab][cix].sum() for cix in reg_cols.values()) * UF
                if _o > 0 and _g > 0:
                    _base.append(_o / _g)
        beta = float(np.median(_base)) if _base else 1.0

        labs_all = sorted(set(d.label) | set(vecs))
        for lab in labs_all + ["ALL"]:
            if lab == "ALL":
                o = d[d.region.notna()].groupby("region")["E"].sum()
                g = pd.Series({r: sum(v[cix].sum() for v in vecs.values()) * UF
                               for r, cix in reg_cols.items()})
            else:
                o = d[(d.label == lab) & d.region.notna()].groupby("region")["E"].sum()
                if lab in vecs:
                    g = pd.Series({r: vecs[lab][cix].sum() * UF for r, cix in reg_cols.items()})
                else:
                    g = pd.Series(0.0, index=list(reg_cols))
            idx = sorted(set(o.index) | set(g.index))
            o, g = o.reindex(idx).fillna(0.0), g.reindex(idx).fillna(0.0)
            both = (o > 0) & (g > 0)
            rows.append(dict(substance=SUB, label=lab, year=Y, n_regions=int(both.sum()),
                             r_linear=corr(o.values, g.values),
                             r_log10=corr(np.log10(o[both].values), np.log10(g[both].values)) if both.sum() > 2 else np.nan,
                             ours_kg=o.sum(), gloria_kg=g.sum(),
                             ratio_ours_over_gloria=o.sum() / g.sum() if g.sum() > 0 else np.inf,
                             beta_vintage=beta,
                             note="households outside GLORIA industry columns" if lab in HH_NOTE else "",
                             abnj_kg=abnj_kg if lab == "1A3d" else 0.0))
            if lab == "1A3d":
                exc  = (o - g).clip(lower=0)                       # raw gap
                exca = (o - beta * g).clip(lower=0)                # vintage-adjusted gap
                for r in idx:
                    if o[r] > 0:
                        ship_rows.append(dict(substance=SUB, year=Y, region=r,
                                              ours_kg=o[r], gloria_kg=g[r],
                                              excess_kg=exc[r], transit_share=exc[r] / o[r],
                                              excess_adj_kg=exca[r],
                                              transit_share_adj=exca[r] / o[r]))
            if lab in ("1A3b_noRES", "1A4_1A5"):
                # GLORIA's industry block holds only the industry-attributable
                # part of road / residential combustion - the remainder is
                # DIRECT HOUSEHOLD emission (final demand, not interindustry)
                hh = (o - beta * g).clip(lower=0)
                for r in idx:
                    if o[r] > 0:
                        hh_rows.append(dict(substance=SUB, label=lab, year=Y, region=r,
                                            ours_kg=o[r], gloria_ind_kg=g[r],
                                            household_kg=hh[r],
                                            household_share=hh[r] / o[r]))

R = pd.DataFrame(rows)
R.to_csv(os.path.join(OUT, "corr_by_label_year.csv"), index=False)
# period means; the level ratio only over years where the GLORIA vector exists
per = (R.groupby(["substance", "label"], as_index=False)
         .agg(years=("year", "nunique"), r_linear=("r_linear", "mean"), r_log10=("r_log10", "mean"),
              ours_kg=("ours_kg", "mean"), gloria_kg=("gloria_kg", "mean")))
_ok = R[R.gloria_kg > 0].groupby(["substance", "label"]) \
       .apply(lambda x: x.ours_kg.mean() / x.gloria_kg.mean()).rename("ratio_ours_over_gloria")
per = per.merge(_ok, on=["substance", "label"], how="left")
per.sort_values(["substance", "ratio_ours_over_gloria"], ascending=[True, False]) \
   .to_csv(os.path.join(OUT, "corr_by_label_period.csv"), index=False)

H = pd.DataFrame(hh_rows)
if len(H):
    H.to_csv(os.path.join(OUT, "household_share_road_residential.csv"), index=False)
    hsum = (H.groupby(["substance", "label", "year"])
              .apply(lambda x: x.household_kg.sum() / x.ours_kg.sum())
              .groupby(["substance", "label"]).mean())
    print("\nDirect-household share of road / residential emissions "
          "(GLORIA industry block as the industry anchor):")
    print(hsum.round(3).to_string())

S = pd.DataFrame(ship_rows)
if len(S):
    S.to_csv(os.path.join(OUT, "transit_share_1A3d.csv"), index=False)
    top = (S[S.substance == "NOx"].groupby("region", as_index=False)
             .agg(ours_kg=("ours_kg", "mean"), gloria_kg=("gloria_kg", "mean"),
                  excess_kg=("excess_kg", "mean"), transit_share=("transit_share", "mean"),
                  excess_adj_kg=("excess_adj_kg", "mean"),
                  transit_share_adj=("transit_share_adj", "mean"))
             .sort_values("excess_adj_kg", ascending=False))
    top.to_csv(os.path.join(OUT, "top_1A3d_discrepancies_NOx.csv"), index=False)

print("\n================ per-label summary (period means) ================")
with pd.option_context("display.width", 160, "display.max_rows", 100):
    print(per.assign(ours_Tg=lambda x: x.ours_kg / 1e9, gloria_Tg=lambda x: x.gloria_kg / 1e9)
             .round({"r_linear": 3, "r_log10": 3, "ratio_ours_over_gloria": 2,
                     "ours_Tg": 2, "gloria_Tg": 2})
             [["substance", "label", "years", "r_linear", "r_log10",
               "ours_Tg", "gloria_Tg", "ratio_ours_over_gloria"]].to_string(index=False))
if len(S):
    g = S[S.substance == "NOx"].groupby("year").agg(ours=("ours_kg", "sum"), glo=("gloria_kg", "sum"),
                                                    exc=("excess_kg", "sum"), exca=("excess_adj_kg", "sum"))
    print("\nNOx 1A3d, global (Tg of NO2):  raw gap and vintage-adjusted gap")
    print((g / 1e9).round(2).assign(transit_share=(g.exc / g.ours).round(3),
                                    transit_share_adj=(g.exca / g.ours).round(3)).to_string())
    print("\nTop 12 regions by unaccounted (transit) shipping NOx, period mean (adjusted):")
    print(top.head(12).assign(ours_kt=lambda x: x.ours_kg / 1e6,
                              excess_adj_kt=lambda x: x.excess_adj_kg / 1e6)
             .round({"ours_kt": 0, "excess_adj_kt": 0, "transit_share_adj": 2})
             [["region", "ours_kt", "excess_adj_kt", "transit_share_adj"]].to_string(index=False))

# ---- Part 2: impact satellite vs GLORIA emissions, per GLORIA industry ------
try:
    import scipy.sparse as sp
    for SUB in ["NOx", "NH3"]:
        sh = []
        for Y in YEARS:
            f = os.path.join(SAT, f"satellite_{SUB}_{Y}.npz")
            files = sorted(glob.glob(os.path.join(G60, SUB, f"GLORIA_{Y}_60_{SUB}*#*.csv")))
            if not (os.path.exists(f) and files):
                continue
            colsum = np.asarray(sp.load_npz(f).sum(axis=0)).ravel()          # kg O2-eq per column
            gall = np.zeros(len(colsum))
            for v in gloria_vec(SUB, Y, files).values():
                gall += v
            df = collab.copy()
            df["impact"], df["gloria"] = colsum, gall
            df = df[df["type"] == "industry"]
            a = df.groupby("sector", as_index=False)[["impact", "gloria"]].sum()
            a["impact_share"] = a.impact / a.impact.sum()
            a["gloria_share"] = a.gloria / a.gloria.sum()
            a["year"] = Y
            sh.append(a)
        if sh:
            A = (pd.concat(sh).groupby("sector", as_index=False)
                   [["impact_share", "gloria_share"]].mean())
            A["share_ratio"] = A.impact_share / A.gloria_share.replace(0, np.nan)
            A.sort_values("impact_share", ascending=False) \
             .to_csv(os.path.join(OUT, f"industry_share_comparison_{SUB}.csv"), index=False)
            t = A.sort_values("impact_share", ascending=False).head(8)
            print(f"\n{SUB}: top industries - share of OUR impact satellite vs share of GLORIA emissions")
            print(t.round(4).to_string(index=False))
except Exception as e:  # satellites are optional for Part 1
    print("Part 2 skipped:", e)

# ---- scatter: ours vs GLORIA, every region x label point, shipping in colour
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
for SUB in ["NOx", "NH3"]:
    sub = R[(R.substance == SUB)]
    if sub.empty:
        continue
    fig, ax = plt.subplots(figsize=(4.6, 4.6), dpi=200)
    src = next((p for p in CAND[SUB] if os.path.exists(p)), None)
    E = pd.read_csv(src).rename(columns={EMISCOL[SUB]: "E", "IPCC_sector": "label"})
    E["label"] = E["label"].replace(ALIAS)
    E["region"] = E["emission_country"].map(c2r)
    pts_x, pts_y, ship_x, ship_y = [], [], [], []
    for Y in YEARS:
        files = sorted(glob.glob(os.path.join(G60, SUB, f"GLORIA_{Y}_60_{SUB}*#*.csv")))
        if not files:
            continue
        vecs = gloria_vec(SUB, Y, files)
        UF = unit_note.get(SUB, 1e6)
        d = E[E.year == Y]
        for lab, v in vecs.items():
            o = d[(d.label == lab) & d.region.notna()].groupby("region")["E"].sum()
            for r, ov in o.items():
                gv = v[reg_cols[r]].sum() * UF if r in reg_cols else 0.0
                if ov > 0 and gv > 0:
                    (ship_x if lab == "1A3d" else pts_x).append(gv)
                    (ship_y if lab == "1A3d" else pts_y).append(ov)
    ax.scatter(pts_x, pts_y, s=4, c="#9aa5b1", alpha=.4, lw=0, label="all other IPCC labels")
    ax.scatter(ship_x, ship_y, s=7, c="#c23b22", alpha=.75, lw=0, label="shipping (1A3d)")
    lim = [1e3, max(pts_y + ship_y + pts_x + ship_x) * 2]
    ax.plot(lim, lim, color="#1a1a1a", lw=.7, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("GLORIA v60 emission account (kg)")
    ax.set_ylabel("this study: EDGAR within land-EEZ (kg)")
    ax.set_title(f"{SUB}: region x IPCC-label emissions, 2015-2022", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"scatter_GLORIA_vs_EEZ_{SUB}.png"))
print("\nwritten ->", OUT)
