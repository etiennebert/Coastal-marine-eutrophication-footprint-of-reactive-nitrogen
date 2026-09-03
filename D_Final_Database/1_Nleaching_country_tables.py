# 1_Nleaching_country_tables.py - LEACHING ONLY: country x sector N tables (Tg)
# ---------------------------------------------------------------------------
# From eutrophication_all_pathways.parquet, WATERBORNE rows only (pathway crop +
# grazing; NOx and NH3 excluded), two tables as period mean over YEARS:
#   TABLE 1  N_released_country_x_sector.csv   N emitted from soils (deposition-
#            free IMAGE surplus), Tg N/yr: one row per PRODUCING COUNTRY, ordered
#            by continent (then largest first); columns = each crop +
#            'Cattle (grazing)' + Total; 'World' row at the bottom.
#   TABLE 2  N_reaching_country_x_sector.csv   same layout, the N actually
#            ENTERING the receiving waters (leaching x Fraction_N_marine, from
#            the harmonised 'delivered_kgN' column - re-run the pipelines and
#            0_harmonise_pathways.py first, else TABLE 2 is NaN).
#   Both sheets also land in N_leaching_country_tables.xlsx (if openpyxl exists).
#
# Countries keep the World_Countries names used by the leaching pipelines - no
# GLORIA mapping involved. The continent (ordering only) comes from
# country_to_continent.csv next to this script; unlisted names go to 'Other'
# and are REPORTED so the csv can be extended.
#
# RUN from inside D_Final_Database:   python 1_Nleaching_country_tables.py
# ---------------------------------------------------------------------------
import os
import numpy as np
import pandas as pd

try:
    HERE = os.path.dirname(os.path.abspath(__file__))        # ...\D_Final_Database
except NameError:
    HERE = os.getcwd()
YEARS = list(range(2015, 2023))
CONT_ORDER = ["Africa", "Americas", "Asia", "Europe", "Oceania", "Other"]

# ---- 1) waterborne rows of the harmonised database --------------------------
H = pd.read_parquet(os.path.join(HERE, "eutrophication_all_pathways.parquet"))
L = H[H["pathway"].isin(["crop", "grazing"]) & H["year"].isin(YEARS)].copy()
print("leaching rows: %s (crop + grazing, %d-%d)" % (f"{len(L):,}", YEARS[0], YEARS[-1]))
L["sector"] = np.where(L["pathway"] == "grazing", "Cattle (grazing)", L["activity"])

if "delivered_kgN" in L.columns and L["delivered_kgN"].notna().any():
    print("delivered N  : using the harmonised 'delivered_kgN' column")
else:
    L["delivered_kgN"] = np.nan
    print("delivered N  : NaN -> TABLE 2 empty. Run c_make_FFmar_XF_basin.py, re-run the two")
    print("               leaching pipelines (PART A + B), then 0_harmonise_pathways.py.")

# ---- 2) continent (for ROW ORDERING only; rows stay per country) ------------
cc = pd.read_csv(os.path.join(HERE, "country_to_continent.csv"))
cmap = dict(cc[["Country", "continent"]].values)
L["continent"] = L["emission_country"].map(cmap).fillna("Other")
un = sorted(L.loc[L["continent"] == "Other", "emission_country"].unique())
if un:
    print("countries not in country_to_continent.csv (%d) -> 'Other':" % len(un))
    print("  " + "; ".join(un[:30]) + (" ..." if len(un) > 30 else ""))

# ---- 3) the two tables: yearly sums -> period mean -> Tg, country x sector --
def table(col, cols=None):
    t = (L.groupby(["year", "continent", "emission_country", "sector"])[col].sum(min_count=1)
           .reset_index()
           .groupby(["continent", "emission_country", "sector"])[col].mean().div(1e9)
           .unstack())                                                          # Tg N / yr
    t = t[cols] if cols is not None else t[t.sum().sort_values(ascending=False).index]
    t["Total"] = t.sum(axis=1, min_count=1)
    t = (t.reset_index()
          .assign(_c=lambda d: pd.Categorical(d["continent"], CONT_ORDER, ordered=True))
          .sort_values(["_c", "Total"], ascending=[True, False]).drop(columns="_c")
          .rename(columns={"emission_country": "country"}).set_index(["continent", "country"]))
    t.loc[("World", ""), :] = t.sum(min_count=1)
    return t.round(4)

t1 = table("release_kgN")
t2 = table("delivered_kgN", cols=[c for c in t1.columns if c != "Total"])   # same column order
print("\nTABLE 1 - N released from soils (Tg N/yr, mean %d-%d): %d countries" %
      (YEARS[0], YEARS[-1], len(t1) - 1))
print(t1.head(12).to_string(), "\n...")
w1, w2 = t1.loc[("World", ""), "Total"], t2.loc[("World", ""), "Total"]
print("World released: %.2f Tg N/yr" % w1)
if pd.notna(w2) and w1 > 0:
    print("World reaching: %.2f Tg N/yr | export fraction %.1f%%" % (w2, 100 * w2 / w1))

# ---- 4) save ----------------------------------------------------------------
t1.to_csv(os.path.join(HERE, "N_released_country_x_sector.csv"))
t2.to_csv(os.path.join(HERE, "N_reaching_country_x_sector.csv"))
try:
    with pd.ExcelWriter(os.path.join(HERE, "N_leaching_country_tables.xlsx"), engine="openpyxl") as w:
        t1.to_excel(w, sheet_name="N released (Tg)")
        t2.to_excel(w, sheet_name="N reaching sea (Tg)")
    print("\nwritten -> 2 csv + N_leaching_country_tables.xlsx")
except ImportError:
    print("\nwritten -> 2 csv (openpyxl missing, no xlsx)")
