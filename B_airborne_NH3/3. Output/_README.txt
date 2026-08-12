3. Output - structure and content  (written by apply_NH3_CF_country_LME.py)
=============================================================================
All impacts in kg O2-equivalent (marine oxygen depletion); emissions in kg NH3.
Every table carries 'year'. Cell_ID = 1-based id on the 91x144 (~2 deg) air grid.

1_impact_tables/   WHO caused it, and WHICH SEA receives it
   NH3_impact_country_to_LME.csv    year x IPCC sector x emitter country x LME
                                    (+ emission_kg and effective CF = impact/emission)
   NH3_impact_by_country_sector.csv marginal: year x sector x emitter country
   NH3_impact_by_LME_sector.csv     marginal: year x sector x LME

2_databases/       the finest building blocks
   NH3_DB1_emissions_cell_country_sector.csv
                                    EMISSIONS ONLY: year x air-cell x emitter
                                    country x sector (country resolved at 0.1 deg)
   NH3_DB2_cell_country_sector_to_LME_<year>.parquet
                                    SELF-CONTAINED: emitting cell x emitter country x
                                    IPCC sector -> every LME it impacts, with emission,
                                    CF_to_LME and eutrophication

3_receptor_countries/   WHOSE WATERS receive it  (modelling ASSUMPTION: impact
                        spread uniformly in the LME, split by EEZ area shares)
   NH3_impact_emitter_LME_receptor.csv   emitter country -> LME -> receptor country
   NH3_impact_by_receptor_country.csv    marginal: year x receptor country

4_per_cell_maps/   WHERE deposition lands on the receptor grid (map layer)
   NH3_impact_per_cell_<year>.csv   impact per receptor cell, summed over ALL
                                    sources (who caused it is in 1_ and 2_)

5_CF_layers/       FACTORS, not results (aggregates of the CF matrix)
   NH3_CF_by_LME.csv                kg O2 per kg emitted, per LME (sum over sources)
   NH3_CF_receptor_map.csv          same per receptor cell - label as AGGREGATE CFs
