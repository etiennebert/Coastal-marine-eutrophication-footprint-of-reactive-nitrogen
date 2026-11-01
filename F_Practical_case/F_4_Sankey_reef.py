# F_4_Sankey_reef.py — producer -> consumer Sankeys, all 7 reef sites on ONE page
# ---------------------------------------------------------------------------
# WHO produces the impact in a reef sub-segment, and WHOSE consumption drives it?
# For sub-segment r:   F(p, c) = sum_{i in region p} q_r(i) * x_cty(i, c)
#   q_r   = satellite row r / gross output x   (kg O2-eq per kUSD, per column)
#   x_cty = L * Y_cty (saved by A_1)           (production embodied in c's demand)
# F is a 164 x 164 producing x consuming region matrix; its row sums are the PBA
# marginals, its column sums the CBA marginals - both CHECKED against E_1's
# CBA_vs_PBA tables at run time.
#
# OUTPUT (in "2. figures/sankey/"), for NOx, NH3, Nleach AND their sum "Total":
#   Sankey_<SUB>_<YEAR>_all_sites.html / .svg / .png   one page, 7 panels (a-g,
#       same order and letters as Figure 1) + how-to-read box; ONE colour per
#       country shared by every panel (anchored on Example_Sankey_2025 palette)
#   Sankey_<SUB>_<YEAR>_<lme>_matrix.csv               producer x consumer table
# Sites with no impact for a substance (e.g. no leaching) show "no data".
#
# RUN (from F_Practical_case):
#   python F_4_Sankey_reef.py                 -> YEAR = 2015 (default)
#   python F_4_Sankey_reef.py 2018            -> any other year already run by E_1
#   python F_4_Sankey_reef.py 2015 transit    -> TRANSIT mode: the share of each
#       country's shipping NOx that exists in NO national account (EDGAR books
#       international navigation under "SEA", not under countries; GLORIA's
#       country rows hold only the domestic part) is moved from the producing
#       country to a pooled left-side node "Int. shipping (at sea)". Shares come
#       from E_MRIO_GLORIA_Satellites/2. GLORIA_vs_EEZ_check/transit_share_1A3d.csv
#       (run 1_check_GLORIA_vs_EEZ_emissions.py first). Totals and the consumer
#       side are unchanged; outputs get the suffix "_transit".
# needs scipy, pandas, numpy, plotly  (pip install kaleido  for svg/png export)
# ---------------------------------------------------------------------------
import os, sys
import numpy as np
import pandas as pd
from scipy.io import loadmat
import plotly.graph_objects as go
import plotly.io as pio

# %% ------------------------------ configuration ---------------------------
YEAR    = int(sys.argv[1]) if len(sys.argv) > 1 else 2015
TRANSIT = any(a.lower() == "transit" for a in sys.argv[2:])
HHMODE  = any(a.lower() == "hh"      for a in sys.argv[2:])
#   "hh" mode: the DIRECT-HOUSEHOLD share of road transport (1A3b) and
#   residential combustion (1A4_1A5) - private driving and home heating, which
#   belong to household final demand, not to the interindustry system - is
#   reassigned to the emitting country's OWN consumer column (producer =
#   consumer). Amounts come exactly from the CF-level pair tables
#   (<SUB>_impact_country_to_LME.csv) weighted by the GLORIA-anchored household
#   shares (household_share_road_residential.csv from 1_check_GLORIA_vs_EEZ_
#   emissions.py); the removal from the row's current consumer profile is
#   pro-rata (the household part's own profile is not separable ex post).
#   Modes compose: "python F_4_Sankey_reef.py 2015 transit hh".
#
#   "anchored" mode (preferred once 2_make_anchored_satellites.py has run):
#   reads the GLORIA-anchored satellite batch from "1b. ..._anchored" plus its
#   per-sector delta satellites, and rebuilds each panel EXACTLY:
#     - anchored satellite -> the interindustry flows (domestic navigation,
#       industry road/residential, everything else unchanged)
#     - dship delta  -> pooled left node "Int. shipping (at sea)" (consumers =
#       the water-transport customer profile the delta carries)
#     - dhh delta    -> booked on the emitting country's own diagonal
#   Marginal checks then compare against "1. results_anchored" if E_1 has been
#   re-run on the anchored batch (skipped otherwise). Supersedes transit/hh.
ANCH = any(a.lower() == "anchored" for a in sys.argv[2:])
if ANCH and (TRANSIT or HHMODE):
    print("anchored mode supersedes transit/hh - flags ignored")
    TRANSIT = HHMODE = False
SUFFIX  = "_anchored" if ANCH else \
          ("_transit" if TRANSIT else "") + ("_hh" if HHMODE else "")
SUBS   = ["NOx", "NH3", "Nleach"]   # a "Total" page (their sum) is added automatically
TOPN   = 6                          # named countries per column; rest pooled grey
MIN_SHARE = 0.015                   # name a country only if it holds >= 1.5% of the total
GLORIA = os.environ.get("GLORIA_ROOT", r"D:\GLORIA_MRIOS_60")   # GLORIA folder with "matrix calc" (same as E_1)

HERE    = os.path.dirname(os.path.abspath(__file__))
SAT_DIR = os.path.join(HERE, "..", "E_MRIO_GLORIA_Satellites",
                       "1b. GLORIAv60_Eutrophication_Satellites_anchored" if ANCH
                       else "1. GLORIAv60_Eutrophication_Satellites")
OUT_DIR = os.path.join(HERE, "2. figures", "sankey")
os.makedirs(OUT_DIR, exist_ok=True)

# sites in Figure-1 order (west -> east) so panel letters a-g match the map
SITES = [("10", "Kane'ohe Bay"), ("12_1", "Bocas del Toro"), ("12_2", "Crocker Reef"),
         ("36_13", "Taiping"), ("36_18", "Dongsha"), ("49", "Okinawa"),
         ("40_4", "Heron Island")]
BORDER = {"10": {"USA"}, "12_1": {"PAN","CRI","NIC","HND","GTM","BLZ","MEX","COL"},
          "12_2": {"USA","CUB","BHS"}, "36_13": {"VNM","PHL","MYS","BRN"},
          "36_18": {"CHN","TWN","PHL"}, "49": {"JPN","TWN"}, "40_4": {"AUS"}}
NAMES = {"CHN":"China","JPN":"Japan","KOR":"South Korea","TWN":"Taiwan","VNM":"Viet Nam",
         "USA":"United States","MEX":"Mexico","NIC":"Nicaragua","CUB":"Cuba","BHS":"Bahamas",
         "AUS":"Australia","IDN":"Indonesia","PHL":"Philippines","MYS":"Malaysia",
         "THA":"Thailand","IND":"India","SGP":"Singapore","BRN":"Brunei","PNG":"Papua N.G.",
         "HND":"Honduras","GTM":"Guatemala","CRI":"Costa Rica","PAN":"Panama","COL":"Colombia",
         "BLZ":"Belize","DOM":"Dominican Rep.","VEN":"Venezuela","JAM":"Jamaica","KHM":"Cambodia",
         "DEU":"Germany","FRA":"France","GBR":"United Kingdom","RUS":"Russia","CAN":"Canada",
         "NZL":"New Zealand","SAU":"Saudi Arabia","ARE":"UAE","BGD":"Bangladesh",
         "PAK":"Pakistan","LKA":"Sri Lanka","MMR":"Myanmar","LAO":"Laos","HKG":"Hong Kong SAR",
         "BRA":"Brazil","ARG":"Argentina","CHL":"Chile","PER":"Peru","ECU":"Ecuador",
         "TTO":"Trinidad & Tobago","HTI":"Haiti","GUY":"Guyana","SUR":"Suriname",
         "ESP":"Spain","NLD":"Netherlands","ITA":"Italy","TLS":"Timor-Leste",
         "SLB":"Solomon Is.","FJI":"Fiji","VUT":"Vanuatu","NCL":"New Caledonia",
         "XAS":"Rest of Asia-Pacific","XAM":"Rest of Americas",
         "XEU":"Rest of Europe","XAF":"Rest of Africa","REST":"Rest of world",
         "INT":"Int. shipping (at sea)","HH":"Households (own use)"}
DISP = {"NOx": "NO<sub>x</sub>", "NH3": "NH<sub>3</sub>",
        "Nleach": "Leached-N", "Total": "Total-N"}

# one colour per country on the WHOLE page - big recurring countries anchored to
# the palette of Example_Sankey_2025/Color_countries.xlsx, the rest drawn from a
# pool of distinct hues in order of global importance (computed below)
ANCHOR = {"CHN": "rgba(237,29,36,1)",  "USA": "rgba(9,47,96,1)",
          "JPN": "rgba(122,78,150,1)", "KOR": "rgba(208,94,48,1)",
          "MEX": "rgba(255,192,0,1)",  "IDN": "rgba(137,229,36,1)",
          "AUS": "rgba(0,153,159,1)",  "IND": "rgba(253,103,31,1)"}
POOL = ["rgba(28,66,137,1)", "rgba(61,127,235,1)", "rgba(3,149,213,1)",
        "rgba(15,87,57,1)",  "rgba(198,112,218,1)","rgba(62,194,128,1)",
        "rgba(140,86,75,1)", "rgba(227,119,194,1)","rgba(188,189,34,1)",
        "rgba(23,190,207,1)","rgba(255,152,150,1)","rgba(174,199,232,1)",
        "rgba(255,187,120,1)","rgba(152,223,138,1)","rgba(196,156,148,1)",
        "rgba(219,219,141,1)","rgba(158,218,229,1)","rgba(247,182,210,1)",
        "rgba(255,235,0,1)", "rgba(84,39,143,1)"]
REST_COL = "rgba(113,113,113,1)"

print(f"YEAR = {YEAR} | mode: {'anchored' if ANCH else ('transit ' if TRANSIT else '') + ('hh' if HHMODE else '') or 'default'}"
      f"   (info only - other years: python F_4_Sankey_reef.py <year>"
      + (" anchored" if ANCH else "") + ")")

# %% --------------------------- shared GLORIA pieces -----------------------
labs = pd.read_csv(os.path.join(SAT_DIR, "satellite_column_labels.csv"))
reg_codes = list(dict.fromkeys(labs["region"]))                # 164, GLORIA order
gidx = np.array([reg_codes.index(r) for r in labs["region"]])  # column -> region

# producer axis: the 164 regions, plus pooled special rows -
# "INT" (international shipping) and, in anchored mode, "HH" (household road
# use, shown as its own source so it stays VISIBLE; its ribbons all flow to
# the emitting country's own consumers and count as domestic)
P_CODES = reg_codes + (["INT", "HH"] if ANCH else (["INT"] if TRANSIT else []))
# in anchored mode the CONSUMER axis gets the same two special nodes: the two
# categories run left->right as their own closed bands (INT->INT, HH->HH) and
# never touch a country - international shipping is unallocable on the consumer
# side by the same logic as on the producer side, and household use IS the
# final consumption itself
C_CODES = reg_codes + (["INT", "HH"] if ANCH else [])
HH_ROW, INT_COL, HH_COL = 165, 164, 165
NP_ROWS, NC_COLS = len(P_CODES), len(C_CODES)
if TRANSIT:
    shipmask = np.array([(t == "industry") and ("Water transport" in l)
                         for l, t in zip(labs["label"], labs["type"])], dtype=float)
    ts_file = os.path.join(SAT_DIR, "..", "2. GLORIA_vs_EEZ_check",
                           "transit_share_1A3d.csv")
    _t = pd.read_csv(ts_file)
    _t = _t[(_t.substance == "NOx") & (_t.year == YEAR)].set_index("region")["transit_share"]
    t_vec = np.clip(np.array([_t.get(r, 0.0) for r in reg_codes]), 0, 1)
    print(f"TRANSIT mode: unassigned shipping shares loaded for {int((_t.index.size))} regions "
          f"(mean over regions with shipping {t_vec[t_vec > 0].mean():.2f})")

if HHMODE:
    HH_LABELS = ["1A3b_noRES", "1A4_1A5"]
    _hhf = os.path.join(SAT_DIR, "..", "2. GLORIA_vs_EEZ_check",
                        "household_share_road_residential.csv")
    _hh = pd.read_csv(_hhf)
    _hh = _hh[_hh.year == YEAR].set_index(["substance", "label", "region"])["household_share"]
    _c2r = pd.read_csv(os.path.join(SAT_DIR, "..", "0. data_GLORIAv60",
                                    "country_to_GLORIA_region.csv")
                       ).set_index("Country")["Code"].to_dict()
    PAIR_CAND = {   # this model tree first, then the author's D: layout as fallback
      "NOx": [os.path.join(HERE, "..", "C_airborne_NOx", "3. Output", "1_impact_tables",
                           "NOx_impact_country_to_LME.csv"),
              r"D:\MIT_Eutrophication_Model\C_airborne_NOx\3. Output\1_impact_tables\NOx_impact_country_to_LME.csv"],
      "NH3": [os.path.join(HERE, "..", "B_airborne_NH3", "3. Output", "1_impact_tables",
                           "NH3_impact_country_to_LME.csv"),
              r"D:\MIT_Eutrophication_Model\B_airborne_NH3\3. Output\1_impact_tables\NH3_impact_country_to_LME.csv"],
    }
    def hh_by_region(sub):
        """(lme variant, region code) -> household-direct impact kg O2, this YEAR."""
        pf = next((p for p in PAIR_CAND[sub] if os.path.exists(p)), None)
        if pf is None:
            print(f"hh mode: no {sub}_impact_country_to_LME.csv found - {sub} left unchanged")
            return {}
        d = pd.read_csv(pf, usecols=["year", "IPCC_sector", "emission_country",
                                     "LME_nb_f_1", "impact_kgO2"])
        d = d[(d.year == YEAR) & d.IPCC_sector.isin(HH_LABELS)]
        d["region"] = d.emission_country.map(_c2r)
        d = d[d.region.notna()]
        d["h"] = [_hh.get((sub, l, r), 0.0) for l, r in zip(d.IPCC_sector, d.region)]
        d["Hkg"] = d.impact_kgO2 * d.h
        out = d.groupby(["LME_nb_f_1", "region"])["Hkg"].sum()
        print(f"hh mode: {sub} household-direct pair impacts loaded from {os.path.basename(pf)}")
        return out
    HHDAT = {}                                    # filled lazily per substance

xfile = os.path.join(GLORIA, "matrix calc", f"x_{YEAR}.mat")
if not os.path.exists(xfile):
    sys.exit(f"No GLORIA output for {YEAR} ({xfile} missing) - run A_1/E_1 for that year first.")
x     = loadmat(xfile)["x"].ravel()
x_cty = loadmat(os.path.join(GLORIA, "matrix calc", f"x_cty_{YEAR}.mat"))["x_cty"]
assert x.size == 39360 and x_cty.shape == (39360, 164)
x_div = np.where(x == 0, 1.0, x)

def _to_str(v):        # loadmat wraps each cell-array label in its own ndarray
    while isinstance(v, np.ndarray):
        v = v.item() if v.size == 1 else v[0]
    return str(v).strip()

# %% ------------- pass 1: compute every panel + write the matrices ---------
panels = {}                                  # (SUB, lme) -> panel dict
Ftot   = {}                                  # lme -> sum of F over the substances
cmp_dir = os.path.join(HERE, "1. results_anchored" if ANCH else "1. results",
                       "CBA_vs_PBA")
for SUB in SUBS + ["Total"]:
    if SUB != "Total":
        satf = os.path.join(SAT_DIR, f"satellite_{SUB}_{YEAR}.mat")
        if not os.path.exists(satf):
            print(f"{SUB}: {os.path.basename(satf)} not found - substance skipped"); continue
        m = loadmat(satf)
        S = m["S"].tocsr()
        rows_sat = [_to_str(r) for r in np.ravel(m["LME_rows"])]

    for lme, site in SITES:
        if SUB == "Total":                   # sum of the substances computed above
            if lme not in Ftot:
                continue
            F = Ftot[lme]; tot = F.sum()
            print(f"{site:15s} Total: total {tot:.3e} kgO2 (sum of the substances checked above)")
        else:
            try:
                ridx = next(i for i, r in enumerate(rows_sat)
                            if r == lme or r == lme + "_0"
                            or (r.endswith("_0") and r[:-2] == lme))
            except StopIteration:
                print(f"{site}: row {lme} not found - skipped"); continue
            q = np.asarray(S[ridx].todense()).ravel() / x_div
            if q.sum() == 0:
                print(f"{site} {SUB}: no impact - skipped"); continue

            # the producer x consumer matrix (164 regions + optional INT row)
            F = np.zeros((NP_ROWS, NC_COLS))
            np.add.at(F[:, :164], gidx, q[:, None] * x_cty)
            tot = F.sum()

            # CHECK against E_1 marginals (same year, same flow) - BEFORE any
            # transit reallocation, which deliberately changes the PBA rows
            chk = os.path.join(cmp_dir, f"{SUB}_{YEAR}_{lme}.csv")
            if os.path.exists(chk):
                c = pd.read_csv(chk).set_index("region")
                pba = np.array([c["PBA_kgO2"].get(r, 0.0) for r in reg_codes])
                cba = np.array([c["CBA_kgO2"].get(r, 0.0) for r in reg_codes])
                dev = max(np.abs(F.sum(1)[:164] - pba).max(),
                          np.abs(F.sum(0)[:164] - cba).max()) / max(tot, 1)
                print(f"{site:15s} {SUB}: total {tot:.3e} kgO2 | marginals vs E_1 max rel dev {dev:.1e}"
                      + ("  OK" if dev < 1e-3 else "  << CHECK"))
            else:
                print(f"{site:15s} {SUB}: total {tot:.3e} kgO2 (no CBA_vs_PBA file to check against)")

            # TRANSIT: move the unaccounted share of each region's shipping
            # from the region's row to the pooled INT row (consumers unchanged;
            # the total is preserved - verified below)
            if TRANSIT and SUB == "NOx":
                F_ship = np.zeros((NP_ROWS, NC_COLS))
                np.add.at(F_ship[:, :164], gidx, (q * shipmask)[:, None] * x_cty)
                T = t_vec[:, None] * F_ship[:164]
                F[:164] -= T
                F[164]  += T.sum(0)
                assert abs(F.sum() - tot) < 1e-6 * max(tot, 1), "transit move lost mass"
                print(f"{'':15s}      shipping {100*F_ship.sum()/tot:.0f}% of site total, "
                      f"of which unassigned (INT) {100*F[164].sum()/tot:.0f}% of site total")

            # HOUSEHOLD: reassign the direct-household share of road/residential
            # to the emitting country's own consumption (removal pro-rata over
            # the row's consumers; amount exact from the CF-level pair tables)
            if HHMODE and SUB in ("NOx", "NH3"):
                if SUB not in HHDAT:
                    HHDAT[SUB] = hh_by_region(SUB)
                Hp = HHDAT[SUB]
                moved = 0.0
                for li, r in enumerate(reg_codes):
                    Hv = 0.0
                    for key in (lme, lme + "_0"):
                        Hv += float(Hp.get((key, r), 0.0)) if len(Hp) else 0.0
                    rs = F[li].sum()
                    if Hv <= 0 or rs <= 0:
                        continue
                    mv = min(Hv, 0.999 * rs)
                    F[li] *= (1 - mv / rs)
                    F[li, li] += mv
                    moved += mv
                assert abs(F.sum() - tot) < 1e-6 * max(tot, 1), "hh move lost mass"
                print(f"{'':15s}      household-direct (road+residential) kept at home: "
                      f"{100*moved/tot:.0f}% of site total")

            # ANCHORED: add the delta satellites back in their honest places -
            # international shipping as a pooled producer with its modeled
            # consumer profile, household road/residential on the diagonal
            if ANCH and SUB in ("NOx", "NH3"):
                import scipy.sparse as _sp
                added = {"dship": 0.0, "dhh": 0.0}
                for kind in ("dship", "dhh"):
                    df_ = os.path.join(SAT_DIR, f"satellite_{kind}_{SUB}_{YEAR}.npz")
                    if not os.path.exists(df_):
                        continue
                    drow = np.asarray(_sp.load_npz(df_).tocsr()[ridx].todense()).ravel()
                    if drow.sum() == 0:
                        continue
                    val = float(drow.sum())          # the delta's impact total (direct sum: keeps
                                                     # mass on zero-output columns, unlike q @ x)
                    if kind == "dship":              # closed band INT -> INT:
                        F[164, INT_COL] += val       # unallocable on BOTH sides
                    else:                            # closed band HH -> HH:
                        F[HH_ROW, HH_COL] += val     # household use IS the demand
                    added[kind] = val
                tot = F.sum()                        # full site total, deltas included
                print(f"{'':15s}      add-backs -> full total {tot:.3e} kgO2 | "
                      f"Int. shipping {100*added['dship']/tot:.0f}% | "
                      f"household (kept at home) {100*added['dhh']/tot:.0f}%")
            Ftot[lme] = Ftot.get(lme, 0) + F

        # is the Sankey worth showing? domestic (producer = consumer) vs traded
        # (HH flows go to their own country -> they COUNT AS DOMESTIC)
        hh_dom  = F[HH_ROW].sum() if (ANCH and F.shape[0] > HH_ROW) else 0.0
        int_un  = F[164].sum() if (ANCH and F.shape[0] > 164) else 0.0
        dom = (np.trace(F[:164, :164]) + hh_dom) / tot
        off = F.copy(); off[:164, :164] -= np.diag(np.diag(F[:164, :164]))
        if ANCH and off.shape[0] > HH_ROW:
            off[164] = 0.0; off[HH_ROW] = 0.0       # special bands are not country trade
        bi, bj = np.unravel_index(np.argmax(off), off.shape)
        print(f"{'':15s}      domestic {100*dom:.0f}% (incl. households)"
              f" | traded {100*(1 - dom - int_un/tot):.0f}%"
              + (f" | unassigned int. shipping {100*int_un/tot:.0f}%" if ANCH else "")
              + f" | largest cross-border flow {P_CODES[bi]}->{C_CODES[bj]}"
                f" {100*off[bi, bj]/tot:.0f}%")

        # top-N per SIDE (producers left, consumers right), the rest pooled;
        # countries below MIN_SHARE stay in the pool so labels never collide
        pv, cv = F.sum(1), F.sum(0)
        top_p = [i for i in np.argsort(pv)[::-1][:TOPN] if pv[i] >= MIN_SHARE * tot]
        top_c = [i for i in np.argsort(cv)[::-1][:TOPN] if cv[i] >= MIN_SHARE * tot]
        rmap = np.full(NP_ROWS, len(top_p)); rmap[top_p] = np.arange(len(top_p))
        cmap = np.full(NC_COLS, len(top_c)); cmap[top_c] = np.arange(len(top_c))
        Fk = np.zeros((len(top_p) + 1, len(top_c) + 1))
        np.add.at(Fk, (rmap[:, None], cmap[None, :]), F)

        p_codes = [P_CODES[i] for i in top_p] + ["REST"]
        c_codes = [C_CODES[i] for i in top_c] + ["REST"]
        pd.DataFrame(Fk, index=[f"P_{c}" for c in p_codes],
                     columns=[f"C_{c}" for c in c_codes]
                     ).to_csv(os.path.join(OUT_DIR, f"Sankey_{SUB}_{YEAR}_{lme}_matrix"
                                                    + SUFFIX + ".csv"))
        panels[(SUB, lme)] = dict(site=site, tot=tot, Fk=Fk,
                                  p_codes=p_codes, c_codes=c_codes)

# %% ------------- one colour per country, shared by all panels -------------
imp = {}
for pn in panels.values():
    for k, v in zip(pn["p_codes"], pn["Fk"].sum(1)): imp[k] = imp.get(k, 0) + v
    for k, v in zip(pn["c_codes"], pn["Fk"].sum(0)): imp[k] = imp.get(k, 0) + v
imp.pop("REST", None); imp.pop("INT", None); imp.pop("HH", None)
COL, pool = {"REST": REST_COL, "INT": "rgba(45,55,72,1)",
             "HH": "rgba(141,110,99,1)"}, POOL.copy()
for k in sorted(imp, key=imp.get, reverse=True):
    COL[k] = ANCHOR.get(k) or (pool.pop(0) if pool else POOL[len(COL) % len(POOL)])

# %% ------------- pass 2: one page per substance (7 panels + legend) -------
def fmt_pow(v):        # 5.4e8 -> '5.4×10⁸' (plotly html superscript)
    e = int(np.floor(np.log10(v))); return f"{v / 10**e:.1f}×10<sup>{e}</sup>"

X_DOM = [(0.012, 0.462), (0.545, 0.995)]
Y_TOP = [0.955, 0.710, 0.465, 0.220]     # top edge of each row of panels
PANEL_H, GAP_Y = 0.180, 0.012

for SUB in SUBS + ["Total"]:
    if not any((SUB, lme) in panels for lme, _ in SITES):
        continue                              # substance skipped in pass 1
    fig = go.Figure()
    ann = []
    for k, (lme, site) in enumerate(SITES):
        r, c = k // 2, k % 2
        x0, x1 = X_DOM[c]; y1 = Y_TOP[r]; y0 = y1 - PANEL_H
        pn = panels.get((SUB, lme))
        letter = "abcdefg"[k]
        if pn is None:
            ann.append(dict(x=(x0+x1)/2, y=(y0+y1)/2, xref="paper", yref="paper",
                            text=f"<b>{letter}  {site}</b> — no data", showarrow=False,
                            font=dict(size=11, color="#999999")))
            continue
        Fk, tot = pn["Fk"], pn["tot"]
        # drop zero-total rows/cols (e.g. an empty REST): plotly discards nodes
        # without links and then mis-assigns the fixed x/y of all later nodes,
        # so every node kept here MUST keep at least one link (all Fk > 0 kept)
        pkeep = [i for i, v in enumerate(Fk.sum(1)) if v > 0]
        ckeep = [j for j, v in enumerate(Fk.sum(0)) if v > 0]
        Fk = Fk[np.ix_(pkeep, ckeep)]
        p_codes = [pn["p_codes"][i] for i in pkeep]
        c_codes = [pn["c_codes"][j] for j in ckeep]
        np_, nc_ = len(p_codes), len(c_codes)

        # nodes: producers (left) then consumers (right), each ordered as built
        # (descending, REST last); explicit x/y keep that order on the page
        def _ys(vals):                       # stacked top->bottom, gaps so labels never collide
            h = np.array(vals) / tot * (1 - GAP_Y * (len(vals) - 1))
            y = np.empty(len(h))
            for k in range(len(h)):          # centre of node k, pushed down if too close
                y[k] = h[k] / 2 if k == 0 else max(
                    y[k-1] + (h[k-1] + h[k]) / 2 + GAP_Y, y[k-1] + 0.040)
            return np.clip(y, 0.001, 0.999)
        pv, cv = Fk.sum(1), Fk.sum(0)
        node_x = [0.001] * np_ + [0.999] * nc_
        node_y = list(_ys(pv)) + list(_ys(cv))
        lab, colr = [], []
        for codes, vals in [(p_codes, pv), (c_codes, cv)]:
            for code, v in zip(codes, vals):
                mark = "" if (code in BORDER[lme] or code in ("REST", "INT", "HH")) else "*"
                pct = 100 * v / tot
                lab.append(f"{NAMES.get(code, code)}{mark} "
                           + (f"{pct:.0f}%" if pct >= 0.5 else "<1%"))
                colr.append(COL[code])
        src, dst, val, lcol = [], [], [], []
        for i in range(np_):
            for j in range(nc_):
                if Fk[i, j] > 0:
                    src.append(i); dst.append(np_ + j); val.append(Fk[i, j])
                    lcol.append(COL[p_codes[i]].replace(",1)", ",0.42)"))
        fig.add_trace(go.Sankey(
            domain=dict(x=[x0, x1], y=[y0, y1]),
            arrangement="fixed", valueformat=".3s", valuesuffix=" kg O2-eq",
            node=dict(pad=8, thickness=12, line=dict(width=0), label=lab,
                      color=colr, x=node_x, y=node_y),
            link=dict(source=src, target=dst, value=val, color=lcol)))
        ann.append(dict(x=x0, y=y1 + 0.013, xref="paper", yref="paper",
                        xanchor="left", yanchor="bottom", showarrow=False,
                        text=f"<b>{letter}  {site} ({lme.replace('_','.')})</b>"
                             f"   {fmt_pow(tot)} kg O<sub>2</sub>-eq",
                        font=dict(size=11.5)))

    # how-to-read box in the free 8th cell
    ann.append(dict(x=X_DOM[1][0], y=Y_TOP[3] - 0.004, xref="paper", yref="paper",
                    xanchor="left", yanchor="top", align="left", showarrow=False,
                    text=("<b>How to read</b><br>"
                          "Left column - countries whose territorial emissions produce the<br>"
                          "impact (production-based). Right column - countries whose final<br>"
                          "consumption drives it (consumption-based). Ribbon width is the<br>"
                          "impact flowing from producer to consumer, in kg O<sub>2</sub>-eq;<br>"
                          "percentages are shares of the sub-segment total.<br>"
                          "* country does not border the sub-segment.<br>"
                          "Grey (Rest of world) = all remaining countries pooled.<br>"
                          + ("Int. shipping (at sea) = within-EEZ ship emissions absent<br>"
                             "from every national account (transit; see Methods).<br>"
                             if TRANSIT else "")
                          + ("Household driving and home heating are booked as the<br>"
                             "emitting country's own consumption (direct emissions).<br>"
                             if HHMODE else "")
                          + ("Int. shipping (at sea) = navigation absent from every<br>"
                             "national account; unallocable on either side, it runs as<br>"
                             "its own closed band. Households (own use) = private road<br>"
                             "use; its consumption is the household itself, so it also<br>"
                             "runs as one band and counts as domestic.<br>"
                             if ANCH else "")
                          + "Colours are identical across panels."),
                    font=dict(size=10.5, color="#333333")))
    ann.append(dict(x=0.5, y=1.022, xref="paper", yref="paper", xanchor="center",
                    yanchor="bottom", showarrow=False,
                    text=f"producing countries (left)  →  consuming countries (right), {YEAR}"
                         + ("  ·  international shipping shown unassigned" if TRANSIT else "")
                         + ("  ·  household emissions kept domestic" if HHMODE else "")
                         + ("  ·  GLORIA-anchored accounting" if ANCH else ""),
                    font=dict(size=12, color="#555555")))
    fig.update_layout(
        title=dict(text=f"<b>{DISP[SUB]}-driven eutrophication of the seven coral-reef "
                        f"sub-segments</b>", x=0.5, xanchor="center",
                   y=0.995, yanchor="top", yref="container", font=dict(size=16)),
        annotations=ann, width=1160, height=1500,
        font=dict(family="Helvetica, Arial", size=10),
        margin=dict(l=10, r=10, t=100, b=15), paper_bgcolor="white")

    base = os.path.join(OUT_DIR, f"Sankey_{SUB}_{YEAR}_all_sites" + SUFFIX)
    fig.write_html(base + ".html")
    try:
        pio.write_image(fig, base + ".svg")
        pio.write_image(fig, base + ".png", scale=2)
        print(f"{SUB}: wrote all-sites .html + .svg + .png")
    except Exception as e:
        first = str(e).strip().split("\n")[0] or "kaleido/Chrome missing"
        print(f"{SUB}: wrote all-sites .html "
              f"(svg/png skipped - pip install kaleido; {first})")

print("DONE - one page per substance + pair matrices in '2. figures/sankey'.")
