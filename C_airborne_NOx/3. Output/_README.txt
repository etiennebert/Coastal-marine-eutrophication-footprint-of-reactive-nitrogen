3. Output - structure and content  (written by apply_NOx_CF_country_LME.py)
=============================================================================
All impacts in kg O2-equivalent (marine oxygen depletion); emissions in kg NOx.
Every table carries 'year'. Cell_ID = 1-based id on the 91x144 (~2 deg) air grid.

1_impact_tables/   WHO caused it, and WHICH SEA receives it
   NOx_impact_country_to_LME.csv    year x IPCC sector x emitter country x LME
                                    (+ emission_kg and effective CF = impact/emission)
   NOx_impact_by_country_sector.csv marginal: year x sector x emitter country
   NOx_impact_by_LME_sector.csv     marginal: year x sector x LME

2_databases/       the finest building blocks
   NOx_DB1_emissions_cell_country_sector.csv
                                    EMISSIONS ONLY: year x air-cell x emitter
                                    country x sector (country resolved at 0.1 deg)
   NOx_DB2_cell_country_sector_to_LME_<year>.parquet
                                    SELF-CONTAINED: emitting cell x emitter country x
                                    IPCC sector -> every LME it impacts, with emission,
                                    CF_to_LME and eutrophication

3_receptor_countries/   WHOSE WATERS receive it  (modelling ASSUMPTION: impact
                        spread uniformly in the LME, split by EEZ area shares)
   NOx_impact_emitter_LME_receptor.csv   emitter country -> LME -> receptor country
   NOx_impact_by_receptor_country.csv    marginal: year x receptor country

4_per_cell_maps/   WHERE deposition lands on the receptor grid (map layer)
   NOx_impact_per_cell_<year>.csv   impact per receptor cell, summed over ALL
                                    sources (who caused it is in 1_ and 2_)

5_CF_layers/       FACTORS, not results (aggregates of the CF matrix)
   NOx_CF_by_LME.csv                kg O2 per kg emitted, per LME (sum over sources)
   NOx_CF_receptor_map.csv          same per receptor cell - label as AGGREGATE CFs
