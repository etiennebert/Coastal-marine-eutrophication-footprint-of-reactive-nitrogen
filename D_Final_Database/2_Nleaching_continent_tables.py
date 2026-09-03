# 2_Nleaching_continent_tables.py - LEACHING ONLY: continent x sector N tables (Tg)
# ---------------------------------------------------------------------------
# From eutrophication_all_pathways.parquet, WATERBORNE rows only (pathway crop +
# grazing; NOx and NH3 excluded), two tables as period mean over YEARS:
#   TABLE 1  N_released_continent_x_sector.csv    N emitted from soils (the
#            deposition-free IMAGE surplus), in Tg N per year:
#            rows = continent of the PRODUCING country, columns = each crop +
#            'Cattle (grazing)' + Total.
#   TABLE 2  N_reaching_continent_x_sector.csv    the same layout, but the N
#            actually ENTERING the receiving sub-segments' water
#            (= eutrophication / CF_marine; the transport loss is 1 - table2/table1).
#   Both sheets also land in N_leaching_continent_tables.xlsx (if openpyxl exists).
#
# delivered N source, in order of preference:
#   (a) the 'delivered_kgN' column written by the corrected 0_harmonise_pathways.py;
#   (b) if absent/empty: computed here as eutrophication_kgO2 / CF_marine from
#       A_agricultural_leaching/"3. CFs"/CF_marine_LME.csv;
#   (c) neither available -> TABLE 2 is all NaN (a note is printed).
#
# Continent of a country: emission_country -> GLORIA code (country_to_GLORIA_region.csv)
# -> continent (GLORIA_region_to_continent.csv), both in
# E_MRIO_GLORIA_Satellites/"0. data_GLORIAv60". Unmatched countries are REPORTED
# and kept in an 'Unmatched' row - extend the country csv if a big one appears.
#
# RUN from inside D_Final_Database:   python 2_Nleaching_continent_tables.py
# ---------------------------------------------------------------------------
import os
import numpy as np
import pandas as pd

try:
    HERE = os.path.dirname(os.path.abspath(__file__))        # ...\D_Final_Database
except NameError:
    HERE = os.getcwd()
ROOT  = os.path.dirname(HERE)                                # ...\Supporting_Information
GDIR  = os.path.join(ROOT, "E_MRIO_GLORIA_Satellites", "0. data_GLORIAv60")
YEARS = list(range(2015, 2023))
ORDER = ["Africa", "Americas", "Asia", "Europe", "Oceania", "Unmatched"]

def first_existing(cands, what):
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit("%s not found; tried: %s" % (what, "; ".join(cands)))

# ---- 1) waterborne rows of the harmonised database --------------------------
H = pd.read_parquet(os.path.join(HERE, "eutrophication_all_pathways.parquet"))
L = H[H["pathway"].isin(["crop", "grazing"]) & H["year"].isin(YEARS)].copy()
print("leaching rows: %s (crop + grazing, %d-%d)" % (f"{len(L):,}", YEARS[0], YEARS[-1]))
L["sector"] = np.where(L["pathway"] == "grazing", "Cattle (grazing)", L["activity"])

# ---- 2) delivered N: harmoniser column, else computed from CF_marine, else NaN
if "delivered_kgN" in L.columns and L["delivered_kgN"].notna().any():
    print("delivered N  : using the harmonised 'delivered_kgN' column")
else:
    cfm_f = os.path.join(ROOT, "A_agricultural_leaching", "3. CFs", "CF_marine_LME.csv")
    if os.path.exists(cfm_f):
        cfm = pd.read_csv(cfm_f)[["LME_nb_f_1", "CF_marine"]]
        for d in (cfm, L):
            d["_key"] = (d["LME_nb_f_1"].astype(str).str.replace(r"\.0$", "", regex=True)
                                                    .str.replace(r"_0$", "", regex=True))
        L = L.merge(cfm[["_key", "CF_marine"]], on="_key", how="left").drop(columns="_key")
        L["delivered_kgN"] = L["eutrophication_kgO2"] / L["CF_marine"]
        print("delivered N  : computed here from CF_marine_LME.csv")
    else:
        L["delivered_kgN"] = np.nan
        print("delivered N  : NO source (no delivered_kgN column, no CF_marine_LME.csv) -> TABLE 2 = NaN")

# ---- 3) continent of the producing country ----------------------------------
c2r = pd.read_csv(first_existing([os.path.join(GDIR, "country_to_GLORIA_region.csv"),
                                  os.path.join(HERE, "country_to_GLORIA_region.csv")],
                                 "country_to_GLORIA_region.csv"))
r2c = pd.read_csv(first_existing([os.path.join(GDIR, "GLORIA_region_to_continent.csv"),
                                  os.path.join(HERE, "GLORIA_region_to_continent.csv")],
                                 "GLORIA_region_to_continent.csv"))
cont = dict(c2r.merge(r2c, left_on="Code", right_on="region_code")[["Country", "continent"]].values)
L["continent"] = L["emission_country"].map(cont).fillna("Unmatched")
un = sorted(L.loc[L["continent"] == "Unmatched", "emission_country"].unique())
if un:
    print("UNMATCHED countries (%d) -> 'Unmatched' row; extend country_to_GLORIA_region.csv:" % len(un))
    print("  " + "; ".join(un[:30]) + (" ..." if len(un) > 30 else ""))

# ---- 4) the two tables: yearly sums -> period mean -> Tg, continent x sector -
def table(col, cols=None):
    t = (L.groupby(["year", "continent", "sector"])[col].sum(min_count=1).reset_index()
           .groupby(["continent", "sector"])[col].mean().div(1e9).unstack())   # Tg N / yr
    t = t.reindex([r for r in ORDER if r in t.index])
    t = t[cols] if cols is not None else t[t.sum().sort_values(ascending=False).index]  # big sectors first
    t["Total"] = t.sum(axis=1, min_count=1)
    t.loc["World"] = t.sum(min_count=1)
    return t.round(3)

t1 = table("release_kgN")
t2 = table("delivered_kgN", cols=[c for c in t1.columns if c != "Total"])   # same column order as TABLE 1
print("\nTABLE 1 - N released from soils (Tg N/yr, mean %d-%d)\n%s" % (YEARS[0], YEARS[-1], t1.to_string()))
print("\nTABLE 2 - N reaching the receiving waters (Tg N/yr)\n%s" % t2.to_string())
if t2["Total"].notna().any() and t1.loc["World", "Total"] > 0:
    print("\nexport fraction (World, reaching/released): %.1f%%"
          % (100 * t2.loc["World", "Total"] / t1.loc["World", "Total"]))

# ---- 5) save ----------------------------------------------------------------
t1.to_csv(os.path.join(HERE, "N_released_continent_x_sector.csv"))
t2.to_csv(os.path.join(HERE, "N_reaching_continent_x_sector.csv"))
try:
    with pd.ExcelWriter(os.path.join(HERE, "N_leaching_continent_tables.xlsx"), engine="openpyxl") as w:
        t1.to_excel(w, sheet_name="N released (Tg)")
        t2.to_excel(w, sheet_name="N reaching sea (Tg)")
    print("\nwritten -> 2 csv + N_leaching_continent_tables.xlsx")
except ImportError:
    print("\nwritten -> 2 csv (openpyxl missing, no xlsx)")
