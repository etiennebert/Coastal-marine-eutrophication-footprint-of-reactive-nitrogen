# F_2_Figures_CBA_PBA.R
# ---------------------------------------------------------------------------
# CASE-STUDY FIGURES (coral-reef cLME sub-segments) - manuscript numbering:
#
#   Fig 2  PBA | CBA in kg O2-eq, one row per area, three bars (N leach, NH3,
#          NOx), each STACKED by bordering vs non-bordering countries
#          (completes Table 1). No year axis: values are the mean over all
#          years found in '1. results' (2015 alone until E_1 runs 2015-2022).
#   Fig 3  sector contributions, PBA only, period mean: every sector >= 5% of
#          the area total, all remaining sectors pooled at the BOTTOM as
#          "Others (sectors <5% each)"; bars stacked by substance.
#   Fig 4  planetary boundary: remaining safe operating space + the SOS 1 = 0
#          sub-segments in absolute terms (unchanged design).
#
# INPUTS   1. results/CBA_vs_PBA/<flow>_<year>_<lme>.csv     (E_1, RUN_PBA)
#          1. results/PBA/<flow>_<year>_<lme>_production_full.csv
#          SI_2_Supplementary Table.xlsx (sheet 'Table S1', col 'SOS 1 (kgO2/subseg)')
# OUTPUT   2. figures/Fig2_PBA_CBA_bordering.{pdf,png}
#          2. figures/Fig3_sectors_PBA.{pdf,png}
#          2. figures/Fig4_planetary_boundary.{pdf,png} + Fig4_remaining_space_data.csv
# RUN      from F_Practical_case (RStudio: Session > Set WD > To Source File Location)
# Palette: Okabe-Ito subset, CVD-validated.
# ---------------------------------------------------------------------------

library(tidyverse)
library(scales)
library(readxl)
library(patchwork)

BASE <- tryCatch(dirname(rstudioapi::getSourceEditorContext()$path),
                 error = function(e) getwd())
# ONE accounting switch for ALL figures (Figs 2, 3, 4 must come from the same batch):
#   TRUE  -> "1. results_anchored" (GLORIA-anchored: household road/rail/postal and unassigned
#            international shipping are separate categories; E_1 with BATCH = 'anchored' and
#            python F_5_sector_tables_from_satellite.py anchored)
#   FALSE -> "1. results" (original territorial accounting; E_1 with BATCH = 'original')
ANCHORED <- TRUE
RES  <- file.path(BASE, if (ANCHORED) "1. results_anchored" else "1. results")
FIG  <- file.path(BASE, "2. figures")
dir.create(FIG, showWarnings = FALSE, recursive = TRUE)

PBA_DIR  <- file.path(RES, "PBA")   # Fig 3 sector tables, same batch as Figs 2 and 4

AREAS <- tribble(              # Figure-1 order (west -> east), letters a-g
  ~lme,    ~area,
  "10",    "Kane'ohe Bay (10)",
  "12_1",  "Bocas del Toro (12_1)",
  "12_2",  "Crocker Reef (12_2)",
  "36_13", "Taiping (36_13)",
  "36_18", "Dongsha (36_18)",
  "49",    "Okinawa (49)",
  "40_4",  "Heron Island (40_4)")

# countries whose coastline borders each sub-segment (as in Table 1; derived
# geometrically from cLME_ss_full x World_Countries)
BORDER <- list(
  "10"    = c("USA"),
  "12_1"  = c("PAN", "CRI", "NIC", "HND", "GTM", "BLZ", "MEX", "COL"),
  "12_2"  = c("USA", "CUB", "BHS"),
  "36_13" = c("VNM", "PHL", "MYS", "BRN"),
  "36_18" = c("CHN", "TWN", "PHL"),
  "49"    = c("JPN", "TWN"),
  "40_4"  = c("AUS"))

SUBSTANCES <- c("Nleach", "NH3", "NOx")
PAL_SUB <- c(Nleach = "#009E73", NH3 = "#0072B2", NOx = "#E69F00")  # validated
LAB_SUB <- c(Nleach = "N leaching", NH3 = "NH₃", NOx = "NOₓ")
PAL_ORI <- c("Non-bordering countries" = "#E69F00", "Bordering countries" = "#0072B2")
Y_LAB   <- expression("eutrophication (kg" ~ O[2] * "-eq" ~ yr^-1 * ")")

THEME <- theme_minimal(base_size = 9) +
  theme(panel.grid.minor = element_blank(),
        panel.grid.major.x = element_blank(),
        strip.text = element_text(face = "bold", size = 8),
        strip.text.y = element_text(angle = 0, hjust = 0),
        legend.position = "bottom",
        legend.title = element_blank(),
        plot.title = element_text(face = "bold", size = 10),
        plot.subtitle = element_text(size = 8, colour = "grey30"),
        axis.title.x = element_blank())

save_fig <- function(p, name, w_mm, h_mm) {
  ggsave(file.path(FIG, paste0(name, ".pdf")), p, width = w_mm, height = h_mm, units = "mm")
  ggsave(file.path(FIG, paste0(name, ".png")), p, width = w_mm, height = h_mm, units = "mm", dpi = 300)
  message("written: 2. figures/", name, ".pdf + .png")
}

# ---------------------------------------------------------------------------
# 0) load the CBA-vs-PBA tables (backbone of Figs 2 and 4)
# ---------------------------------------------------------------------------
cmp_files <- list.files(file.path(RES, "CBA_vs_PBA"), pattern = "\\.csv$", full.names = TRUE)
if (length(cmp_files) == 0)
  stop("no files in '", basename(RES), "/CBA_vs_PBA' - run E_1_Consumption_eutrophication_LME.m ",
       "(RUN_PBA = true, BATCH = '", if (ANCHORED) "anchored" else "original", "') first.")
cmp <- map_dfr(cmp_files, function(f) {
  m <- str_match(basename(f), "^(Nleach|NH3|NOx)_(\\d{4})_(.+)\\.csv$")
  if (is.na(m[1])) return(NULL)
  read_csv(f, show_col_types = FALSE) |>
    mutate(flow = m[2], year = as.integer(m[3]), lme = m[4])
}) |>
  inner_join(AREAS, by = "lme") |>
  mutate(area      = factor(area, levels = AREAS$area),
         substance = factor(flow, levels = SUBSTANCES))
yrs <- sort(unique(cmp$year))
message("years found: ", paste(yrs, collapse = ", "),
        if (length(yrs) < 8) "  << values below are the mean of these years only" else "")

# ---------------------------------------------------------------------------
# 1) FIGURE 2 - PBA | CBA, stacked bordering vs non-bordering (mean over years)
# ---------------------------------------------------------------------------
f2 <- cmp |>
  mutate(origin = if_else(map2_lgl(region, lme, ~ .x %in% BORDER[[.y]]),
                          "Bordering countries", "Non-bordering countries")) |>
  group_by(area, year, substance, origin) |>
  summarise(PBA = sum(PBA_kgO2), CBA = sum(CBA_kgO2), .groups = "drop") |>
  group_by(area, substance, origin) |>
  summarise(PBA = mean(PBA), CBA = mean(CBA), .groups = "drop") |>   # period mean
  pivot_longer(c(PBA, CBA), names_to = "side", values_to = "kgO2") |>
  mutate(side   = factor(side, c("PBA", "CBA"),
                         labels = c("Production (PBA)", "Consumption (CBA)")),
         origin = factor(origin, c("Non-bordering countries", "Bordering countries")))

p2 <- ggplot(f2, aes(substance, kgO2, fill = origin)) +
  geom_col(colour = "white", linewidth = 0.25, width = 0.65) +
  facet_grid(rows = vars(area), cols = vars(side), scales = "free_y") +
  scale_fill_manual(values = PAL_ORI, breaks = names(PAL_ORI)) +
  scale_x_discrete(labels = LAB_SUB) +
  scale_y_continuous(labels = label_number(scale_cut = cut_short_scale())) +
  labs(y = Y_LAB) + THEME
p2 <- p2 + plot_annotation(
  caption = str_wrap(paste0("Mean over ", paste(range(yrs), collapse = "-"),
                   " (", length(yrs), " year(s)). Bordering countries as in Table 1. ",
                   "Per bar, production and consumption totals are equal by mass balance;",
                   " the bordering share differs."), 100))
save_fig(p2, "Fig2_PBA_CBA_bordering", 180, 230)

# the numbers behind Fig 2, for the text
f2 |> group_by(area, side) |>
  summarise(nonborder_pct = 100 * sum(kgO2[origin == "Non-bordering countries"]) / sum(kgO2),
            total_kgO2 = sum(kgO2), .groups = "drop") |>
  write_csv(file.path(FIG, "Fig2_bordering_shares.csv"))

# ---------------------------------------------------------------------------
# 2) FIGURE 3 - sector contributions, PBA only, >=5% + pooled "Others" at bottom
# ---------------------------------------------------------------------------
pba_files <- list.files(PBA_DIR, pattern = "_production_full\\.csv$", full.names = TRUE)
pba_yrs <- unique(str_match(basename(pba_files), "_(\\d{4})_")[, 2])
if (!setequal(as.integer(pba_yrs), yrs))
  stop("PBA tables cover year(s) ", paste(sort(pba_yrs), collapse = ", "),
       " but CBA_vs_PBA covers ", paste(yrs, collapse = ", "),
       " - run F_5_sector_tables_from_satellite.py", if (ANCHORED) " anchored" else "",
       " for the same years (the period mean must use one consistent year set).")
pba_d <- map_dfr(pba_files, function(f) {
  m <- str_match(basename(f), "^(Nleach|NH3|NOx)_(\\d{4})_(.+?)_production_full\\.csv$")
  if (is.na(m[1])) return(NULL)
  read_csv(f, show_col_types = FALSE) |>
    mutate(flow = m[2], year = as.integer(m[3]), lme = m[4])
})
OTHERS <- "Others (sectors <5% each)"
sec <- pba_d |>
  inner_join(AREAS, by = "lme") |>
  mutate(area = factor(area, levels = AREAS$area),
         substance = factor(flow, levels = SUBSTANCES)) |>
  group_by(area, year, sector, substance) |>
  summarise(kg = sum(kgO2), .groups = "drop") |>
  group_by(area, sector, substance) |>
  summarise(kg = sum(kg) / n_distinct(pba_d$year), .groups = "drop") |>   # period mean
  group_by(area) |>
  mutate(share_sector = ave(kg, sector, FUN = sum) / sum(kg)) |>
  ungroup() |>
  mutate(label = if_else(share_sector >= 0.05, str_trunc(sector, 42), OTHERS)) |>
  group_by(area, label, substance) |>
  summarise(kg = sum(kg), .groups = "drop")

panels <- list()
for (a in intersect(levels(sec$area), unique(as.character(sec$area)))) {
  dd <- filter(sec, area == a)
  lv <- dd |> group_by(label) |> summarise(k = sum(kg), .groups = "drop") |>
    arrange(k) |> pull(label)
  lv <- c(OTHERS, setdiff(lv, OTHERS))          # Others pinned at the BOTTOM
  dd$label <- factor(dd$label, levels = lv)
  panels[[a]] <- ggplot(dd, aes(kg, label, fill = substance)) +
    geom_col(colour = "white", linewidth = 0.25, width = 0.72) +
    scale_fill_manual(values = PAL_SUB, labels = LAB_SUB, drop = FALSE) +
    scale_x_continuous(labels = label_number(scale_cut = cut_short_scale())) +
    labs(subtitle = a, x = NULL, y = NULL) + THEME +
    theme(plot.subtitle = element_text(face = "bold", colour = "black"))
}
fig3 <- wrap_plots(panels, ncol = 2, guides = "collect") &
  theme(legend.position = "bottom")
fig3 <- fig3 + plot_annotation(
  tag_levels = "a",            # panel letters a-g, same order as Figure 1
  caption = str_wrap(paste0("Production-based sector contributions, mean over ",
                   paste(range(yrs), collapse = "-"), "; kg O2-eq per year. Sectors below 5% of an",
                   " area's total are pooled into 'Others' - the leaching pathway (green) sits",
                   " largely inside that bar wherever individual crop sectors stay below 5%.",
                   if (ANCHORED) paste0(" Accounting anchored to GLORIA: 'Road transport -",
                   " household' is direct household emission (private driving; incl. the road",
                   " shares GLORIA books to rail and postal industries), and 'Water transport -",
                   " international (unassigned)' is navigation absent from every national",
                   " account.") else ""), 100))
save_fig(fig3, "Fig3_sectors_PBA", 190, 245)

# ---------------------------------------------------------------------------
# 3) FIGURE 4 - planetary boundary: remaining safe operating space
# ---------------------------------------------------------------------------
sos_file <- file.path(BASE, "SI_2_Supplementary Table.xlsx")
sos <- read_excel(sos_file, sheet = "Table S1", skip = 2) |>
  select(lme = `# Subsegment`, SOS = `SOS 1 (kgO2/subseg)`) |>
  mutate(lme = str_remove(as.character(lme), "_0$"), SOS = as.numeric(SOS)) |>
  filter(!is.na(SOS)) |>
  distinct(lme, .keep_all = TRUE)

# CUMULATIVE framing: SOS 1 is a budget depleted by the summed pressure since 2015
pb <- cmp |>
  group_by(area, lme, year) |>
  summarise(I = sum(PBA_kgO2), .groups = "drop") |>
  left_join(sos, by = "lme") |>
  group_by(area) |>
  arrange(year, .by_group = TRUE) |>
  mutate(Icum = cumsum(I),
         remaining_kg = SOS - Icum,
         remaining_sh = if_else(SOS > 0, 100 * remaining_kg / SOS, NA_real_),
         occupancy_sh = if_else(SOS > 0, 100 * Icum / SOS, NA_real_)) |>
  ungroup()
if (any(is.na(pb$SOS)))
  warning("no SOS found for: ", paste(unique(pb$lme[is.na(pb$SOS)]), collapse = ", "))
pbA <- filter(pb, SOS > 0)
pbB <- filter(pb, SOS == 0)

slope_of <- function(sh, yr) if (n_distinct(yr) >= 2) unname(coef(lm(sh ~ yr))[2]) else NA_real_
trend <- pbA |>
  filter(!is.na(remaining_sh)) |>
  group_by(area) |>
  summarise(pp_yr = slope_of(remaining_sh, year), .groups = "drop") |>
  filter(!is.na(pp_yr))
lastA <- pbA |> group_by(area) |> slice_max(year, n = 1) |> ungroup() |>
  left_join(trend, by = "area") |>
  mutate(exhaust = if_else(!is.na(pp_yr) & pp_yr < 0, year + remaining_sh / (-pp_yr), NA_real_),
         lbl = case_when(
           is.na(pp_yr)                 ~ sprintf("%s\n%.1f%%", as.character(area), remaining_sh),
           !is.na(exhaust) & exhaust <= 2200 ~ sprintf("%s\n%.1f%% · −%.2f pp/yr · exhausted ~%d",
                                                       as.character(area), remaining_sh, -pp_yr, round(exhaust)),
           TRUE                         ~ sprintf("%s\n%.1f%% · −%.2f pp/yr",
                                                  as.character(area), remaining_sh, -pp_yr))) |>
  arrange(remaining_sh) |>
  mutate(y_lbl = purrr::accumulate(remaining_sh, ~ max(.y, .x + 1.5)))  # de-collide labels upward
palA <- setNames(rep(c("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00"),
                     length.out = nlevels(droplevels(pbA$area))),
                 levels(droplevels(pbA$area)))
p_top <- ggplot(pbA, aes(year, remaining_sh, colour = area)) +
  geom_hline(yintercept = 100, colour = "grey70", linewidth = 0.3) +
  { if (length(yrs) > 1) geom_line(linewidth = 0.7) } +
  geom_point(size = 2.2) +
  geom_text(data = lastA, aes(y = y_lbl, label = lbl), hjust = -0.05, size = 2.5,
            lineheight = 0.95, show.legend = FALSE) +
  scale_colour_manual(values = palA) +
  scale_x_continuous(breaks = yrs, expand = expansion(mult = c(0.04, 0.50))) +
  scale_y_continuous(labels = label_number(suffix = "%")) +
  labs(title = "Safe operating space still available",
       subtitle = "share of SOS 1 not yet consumed by the cumulative pressure since 2015 (zoomed axis)",
       y = "% of SOS 1 still available") + THEME +
  theme(legend.position = "none")
p_bot <- ggplot(pbB, aes(year, Icum)) +
  geom_col(fill = "#B2182B", colour = "white", linewidth = 0.25, width = 0.6) +
  geom_text(data = pbB |> group_by(area) |> slice_max(year, n = 1) |> ungroup(),
            aes(label = label_number(scale_cut = cut_short_scale())(Icum)),
            vjust = -0.35, size = 2.4) +
  facet_wrap(vars(area), nrow = 1) +
  scale_x_continuous(breaks = seq(min(yrs), max(yrs), by = 2)) +
  scale_y_continuous(labels = label_number(scale_cut = cut_short_scale()),
                     expand = expansion(mult = c(0, 0.18))) +
  labs(title = "Sub-segments with no space at all (SOS 1 = 0)",
       subtitle = "cumulative overshoot since 2015 - the boundary allows no additional pressure",
       y = paste0("cumulative ", Y_LAB)) + THEME
fig4 <- (p_top / p_bot) + plot_layout(heights = c(1.15, 1)) + plot_annotation(
  tag_levels = "a",            # panels a (space left) / b (boundary consumed)
  caption = str_wrap(paste0("Cumulative pressure = all three pathways summed from 2015, all ",
                   "emitting countries (production total = consumption total). ",
                   "SOS 1 from SI Table S1. ", paste(range(yrs), collapse = "-"), "."), 100))
save_fig(fig4, "Fig4_planetary_boundary", 190, 150)

write_csv(pb |> left_join(trend, by = "area") |>
            arrange(area, year) |>
            select(area, lme, year, SOS_kgO2 = SOS, impact_kgO2 = I,
                   cumulative_kgO2 = Icum, remaining_kgO2 = remaining_kg,
                   remaining_pct = remaining_sh, consumed_pct = occupancy_sh,
                   erosion_pp_per_yr = pp_yr),
          file.path(FIG, "Fig4_remaining_space_data.csv"))
message("ALL DONE - Fig2/Fig3/Fig4 + data csvs in '2. figures'.")
