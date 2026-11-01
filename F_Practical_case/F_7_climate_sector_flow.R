# F_7_climate_sector_flow.R - climate zones x sector groups x nitrogen pathways
# ---------------------------------------------------------------------------
# INPUT   1. results/F6_database/F6_database_{NOx,NH3,Nleach}_<YEAR>.csv  (F_6)
# One panel per CLIMATE ZONE of the receiving cLME sub-segment (Polar ...
# Tropical); in each, five sector groups with ONE BAR PER PATHWAY (leached N,
# NH3, NOx), expressed as % of the WORLD total - all bars over all panels sum
# to 100%:
#   Agriculture                  crops, livestock, fishing, forestry
#   Industry & services          everything else (original = anchored there)
#   Domestic transport           ANCHORED value of the transport sectors
#   International shipping       water-transport difference (orig - anchored)
#   Household driving            road/rail/postal difference (orig - anchored)
# OUTPUT  2. figures/Fig_climate_sector_flow_<YEAR>.{pdf,png} + _data.csv
# RUN     from F_Practical_case, after F_6:   Rscript F_7_climate_sector_flow.R
# ---------------------------------------------------------------------------
library(tidyverse)
library(scales)

YEAR <- 2015                                     # match the F_6 run
BASE <- tryCatch(dirname(rstudioapi::getSourceEditorContext()$path),
                 error = function(e) getwd())
DB   <- file.path(BASE, "1. results", "F6_database")
FIG  <- file.path(BASE, "2. figures")
dir.create(FIG, showWarnings = FALSE, recursive = TRUE)

TRANSPORT <- c("Water transport", "Road transport", "Rail transport",
               "Postal and courier services", "Air transport")
ROADKEY   <- c("Road transport", "Rail transport", "Postal and courier services")
is_agri <- function(s) str_starts(s, "Growing") | str_starts(s, "Raising") |
                       s %in% c("Fishing", "Aquaculture", "Forestry; logging")

d <- map_dfr(c("NOx", "NH3", "Nleach"), function(p) {
  f <- file.path(DB, sprintf("F6_database_%s_%d.csv", p, YEAR))
  if (!file.exists(f)) { warning(p, ": ", basename(f), " missing - run F_6 first"); return(NULL) }
  read_csv(f, col_types = "icccccdd") |>
    group_by(path, climate, sector) |>
    summarise(orig = sum(eutrophication_kgO2), anch = sum(anchored_kgO2), .groups = "drop")
})

d <- d |> mutate(
  group = case_when(
    is_agri(sector)        ~ "Agriculture",
    sector %in% TRANSPORT  ~ "transport",
    TRUE                   ~ "Industry & services"))

sec <- bind_rows(
  d |> filter(group != "transport") |>
    group_by(climate, path, group) |> summarise(kg = sum(orig), .groups = "drop"),
  d |> filter(group == "transport") |>
    group_by(climate, path) |> summarise(kg = sum(anch), .groups = "drop") |>
    mutate(group = "Domestic transport"),
  d |> filter(sector == "Water transport") |>
    group_by(climate, path) |> summarise(kg = sum(orig - anch), .groups = "drop") |>
    mutate(group = "International shipping"),
  d |> filter(sector %in% ROADKEY) |>
    group_by(climate, path) |> summarise(kg = sum(orig - anch), .groups = "drop") |>
    mutate(group = "Household driving"))

stopifnot(abs(sum(sec$kg) - sum(d$orig)) < 1e-3 * sum(d$orig))   # groups tile the total
sec <- sec |> mutate(pct = 100 * kg / sum(kg)) |> filter(kg > 0)

ZONES  <- c("Polar", "Subpolar", "Temperate", "Subtropical", "Tropical")
GROUPS <- c("Agriculture", "Industry & services", "Domestic transport",
            "International shipping", "Household driving")
PAL_SUB <- c(Nleach = "#009E73", NH3 = "#0072B2", NOx = "#E69F00")   # as F_2, CVD-safe
LAB_SUB <- c(Nleach = "Leached N", NH3 = expression(NH[3]), NOx = expression(NO[x]))

sec <- sec |> mutate(climate = factor(climate, ZONES),
                     group   = factor(group, rev(GROUPS)),
                     path    = factor(path, c("Nleach", "NH3", "NOx")),
                     txt     = if_else(pct >= 0.05, sprintf("%.1f", pct), "<0.1"))

fig <- ggplot(sec, aes(pct, group, fill = path)) +
  geom_col(position = position_dodge2(preserve = "single", padding = 0.10),
           colour = "white", linewidth = 0.2, width = 0.82) +
  geom_text(aes(label = txt),
            position = position_dodge2(width = 0.82, preserve = "single", padding = 0.10),
            hjust = -0.16, size = 2.2, colour = "grey25") +
  facet_grid(climate ~ ., switch = "y") +
  scale_fill_manual(values = PAL_SUB, labels = LAB_SUB, name = NULL) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.10)),
                     labels = label_number(suffix = "%")) +
  labs(x = "share of global eutrophication (%)", y = NULL,
       caption = str_wrap(paste0(
         "Nitrogen-driven marine eutrophication ", YEAR, " by climate zone of the ",
         "receiving cLME sub-segment, sector group and pathway, as percentage of the ",
         "world total (all bars over all panels sum to 100%). Domestic transport is ",
         "the GLORIA-anchored value of the transport sectors; international shipping ",
         "and household driving are the two components of the difference between the ",
         "original and anchored accounts."), 76)) +
  theme_minimal(base_size = 9) +
  theme(panel.grid.major.y = element_blank(), panel.grid.minor = element_blank(),
        strip.placement = "outside",
        strip.text.y.left = element_text(angle = 0, face = "bold", hjust = 1),
        panel.spacing.y = unit(3, "mm"),
        legend.position = "bottom", plot.caption = element_text(size = 6.8, hjust = 0),
        plot.margin = margin(4, 14, 4, 4))

ggsave(file.path(FIG, sprintf("Fig_climate_sector_flow_%d.pdf", YEAR)), fig,
       width = 150, height = 235, units = "mm")
ggsave(file.path(FIG, sprintf("Fig_climate_sector_flow_%d.png", YEAR)), fig,
       width = 150, height = 235, units = "mm", dpi = 300)
sec |> select(-txt) |> arrange(climate, group, path) |>
  write_csv(file.path(FIG, sprintf("Fig_climate_sector_flow_%d_data.csv", YEAR)))
message("written -> Fig_climate_sector_flow_", YEAR, ".pdf/.png + _data.csv")
