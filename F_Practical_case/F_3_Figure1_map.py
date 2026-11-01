# F_3_Figure1_map.py — Figure 1: coral-reef case-study sites + their cLME sub-segments
# World overview (Robinson) + one regional inset per site, sub-segment coloured by the
# MEAN 2015-2022 eutrophication intensity (kg O2-eq per km2, all three pathways),
# computed here from 1. results/CBA_vs_PBA (all flows, all years found).
# Areas are the sub-segment polygon areas (equal-area EPSG:6933) — the shapefile's
# Area_km2 attribute holds the PARENT LME area for most rows and must not be used.
# Inputs: cLME_ss_full.shp, World_Countries.shp, 1. results/CBA_vs_PBA/*.csv
import warnings; warnings.filterwarnings("ignore")
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.colors import LogNorm
from matplotlib.gridspec import GridSpec

# shapefiles: the repo's 0_shape_files folder (download it from the Zenodo record;
# set EUTRO_SHAPES to use another location)
import os
SHP = os.environ.get("EUTRO_SHAPES",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "0_shape_files"))
LME = gpd.read_file(os.path.join(SHP, "2_LME shape files", "cLME_ss_full.shp"))
WLD = gpd.read_file(os.path.join(SHP, "1_World_Countries", "World_Countries.shp"))

# site table: label, name, reef lat/lon (Pannier Table 1, lat/lon corrected)
SITES = [  # ordered west -> east for panel letters
    dict(ss="10",    name="Kaneʻohe Bay",       lat=21.458,  lon=-157.798),
    dict(ss="12_1",  name="Bocas del Toro",     lat=9.377,   lon=-82.300),
    dict(ss="12_2",  name="Crocker Reef",       lat=24.909,  lon=-80.526),
    dict(ss="36_13", name="Taiping",            lat=10.377,  lon=114.370),
    dict(ss="36_18", name="Dongsha",            lat=20.707,  lon=116.721),
    dict(ss="49",    name="Okinawa",            lat=26.452,  lon=127.795),
    dict(ss="40_4",  name="Heron Island",       lat=-23.444, lon=151.913),
]
FOCUS = [s["ss"] for s in SITES]
Lf = LME[LME["LME_nb_f_1"].isin(FOCUS)].copy()

# ---- mean 2015-2022 intensity, computed from E_1's CBA_vs_PBA tables ----
import glob, re
import pandas as pd
import numpy as np
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1. results", "CBA_vs_PBA")
tot = {}                                   # (sub-segment, year) -> kg O2, all flows summed
for f in glob.glob(os.path.join(RES, "*.csv")):
    m = re.match(r"(Nleach|NH3|NOx)_(\d{4})_(.+)\.csv$", os.path.basename(f))
    if not m or m.group(3) not in FOCUS:
        continue
    key = (m.group(3), int(m.group(2)))
    tot[key] = tot.get(key, 0.0) + pd.read_csv(f)["PBA_kgO2"].sum()
years = sorted({y for _, y in tot})
print(f"intensities = mean over {years[0]}-{years[-1]} ({len(years)} years)")
area_km2 = dict(zip(Lf["LME_nb_f_1"], Lf.to_crs(6933).geometry.area / 1e6))
inten = {ss: np.mean([tot[(ss, y)] for y in years if (ss, y) in tot]) / area_km2[ss]
         for ss in FOCUS}
for s in SITES:
    s["inten"] = inten[s["ss"]]
    print(f"  {s['name']:15s} {s['inten']:10.1f} kg O2-eq/km2  (area {area_km2[s['ss']]:,.0f} km2)")
Lf["inten"] = Lf["LME_nb_f_1"].map(inten)

# ---- style
mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5,
                     "axes.linewidth": 0.4, "text.color": "#1a1a1a"})
LAND, LANDEDGE, SEA = "#e6e4de", "#ffffff", "#f4f8fb"
CMAP = plt.get_cmap("YlGnBu")
NORM = LogNorm(vmin=0.2, vmax=2500)
STAR_KW = dict(marker="*", s=110, facecolor="#ffd400", edgecolor="black", linewidth=0.6, zorder=6)

fig = plt.figure(figsize=(7.2, 7.6), dpi=200)
gs = GridSpec(3, 4, figure=fig, height_ratios=[2.35, 1, 1], hspace=0.34, wspace=0.12,
              left=0.015, right=0.985, top=0.965, bottom=0.075)

# ---- world overview (Robinson)
axw = fig.add_subplot(gs[0, :]); axw.set_facecolor(SEA)
ROB = "ESRI:54030"
WLD.to_crs(ROB).plot(ax=axw, color=LAND, edgecolor=LANDEDGE, linewidth=0.25)
Lf.to_crs(ROB).plot(ax=axw, color=[CMAP(NORM(v)) for v in Lf["inten"]],
                    edgecolor="#08306b", linewidth=0.6, alpha=0.95)
pts = gpd.GeoDataFrame(SITES, geometry=gpd.points_from_xy([s["lon"] for s in SITES],
                                                          [s["lat"] for s in SITES]), crs=4326).to_crs(ROB)
letters = "abcdefg"
off = {"10": (-34, 3), "12_1": (-8, -16), "12_2": (6, 8), "36_13": (-30, -14),
       "36_18": (-38, 8), "49": (10, 6), "40_4": (8, -6)}
for (i, s), geom in zip(enumerate(SITES), pts.geometry):
    axw.annotate(f"{letters[i]}  {s['name']}", xy=(geom.x, geom.y),
                 xytext=off[s["ss"]], textcoords="offset points", fontsize=7,
                 fontweight="bold", color="#1a1a1a",
                 arrowprops=dict(arrowstyle="-", lw=0.5, color="#666666", shrinkB=2))
    axw.scatter(geom.x, geom.y, **STAR_KW)
axw.set_xticks([]); axw.set_yticks([])
for sp in axw.spines.values(): sp.set_visible(False)
# crop Antarctica / far north: Robinson y for lat -58 and +80
_clip = gpd.GeoSeries(gpd.points_from_xy([0, 0], [-58, 80]), crs=4326).to_crs(ROB)
axw.set_ylim(_clip.geometry.y.iloc[0], _clip.geometry.y.iloc[1])

# ---- regional insets
for i, s in enumerate(SITES):
    ax = fig.add_subplot(gs[1 + i // 4, i % 4]); ax.set_facecolor(SEA)
    poly = Lf[Lf["LME_nb_f_1"] == s["ss"]]
    x0, y0, x1, y1 = poly.total_bounds
    mx, my = max((x1 - x0) * 0.35, 2.5), max((y1 - y0) * 0.35, 2.5)
    # square-ish window around subsegment + reef
    x0, x1 = min(x0, s["lon"]) - mx, max(x1, s["lon"]) + mx
    y0, y1 = min(y0, s["lat"]) - my, max(y1, s["lat"]) + my
    dx, dy = x1 - x0, y1 - y0
    if dx > dy: y0, y1 = (y0 + y1 - dx) / 2, (y0 + y1 + dx) / 2
    else:       x0, x1 = (x0 + x1 - dy) / 2, (x0 + x1 + dy) / 2
    LME.cx[x0:x1, y0:y1].plot(ax=ax, facecolor="none", edgecolor="#9db8cc", linewidth=0.35)
    WLD.cx[x0:x1, y0:y1].plot(ax=ax, color=LAND, edgecolor=LANDEDGE, linewidth=0.3)
    poly.plot(ax=ax, color=CMAP(NORM(s["inten"])), edgecolor="#08306b", linewidth=0.7, alpha=0.95)
    ax.scatter(s["lon"], s["lat"], **STAR_KW)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color("#cccccc"); sp.set_linewidth(0.5)
    ax.set_title(f"{letters[i]}  {s['name']}  ({s['ss'].replace('_', '.')})",
                 fontsize=7.3, fontweight="bold", loc="left", pad=2.5)
    _iv = f"{s['inten']:,.0f}" if s["inten"] >= 1 else f"{s['inten']:.1f}"
    ax.text(0.03, 0.04, f"{_iv} kg O$_2$ km$^{{-2}}$", transform=ax.transAxes,
            fontsize=6.6, ha="left", va="bottom",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#bbbbbb", lw=0.4, alpha=0.9))

# last empty cell -> legend/colorbar block (colorbar on top, items well below)
axl = fig.add_subplot(gs[2, 3]); axl.axis("off")
cax = axl.inset_axes([0.08, 0.80, 0.84, 0.09])
cb = mpl.colorbar.ColorbarBase(cax, cmap=CMAP, norm=NORM, orientation="horizontal")
cb.ax.tick_params(labelsize=6, pad=1.5)
axl.text(0.50, 0.56, "mean eutrophication intensity 2015\u20132022\n(kg O$_2$-eq km$^{-2}$, all pathways)",
         transform=axl.transAxes, fontsize=6.6, ha="center", va="center")
axl.scatter(0.13, 0.34, transform=axl.transAxes, **STAR_KW)
axl.text(0.21, 0.34, "coral-reef site", transform=axl.transAxes, fontsize=6.8, va="center")
axl.add_patch(mpl.patches.Rectangle((0.09, 0.12), 0.08, 0.10, transform=axl.transAxes,
              facecolor="none", edgecolor="#9db8cc", lw=0.8))
axl.text(0.21, 0.17, "other cLME sub-segments", transform=axl.transAxes, fontsize=6.8, va="center")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "2. figures")
os.makedirs(OUT, exist_ok=True)
fig.savefig(os.path.join(OUT, "Fig1_map.png"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(OUT, "Fig1_map.pdf"), bbox_inches="tight")
print("saved 2. figures/Fig1_map.png + .pdf")
