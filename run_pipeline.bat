@echo off
REM ===========================================================================
REM  run_pipeline.bat  -  launch the nitrogen pipeline steps one after another
REM
REM  Default: the full rerun needed after the Nov 2026 units fix and the switch to
REM  year-specific crop weights: crop -> NH3 -> NOx -> harmonise -> satellites ->
REM  anchored batch -> (MATLAB E_1 pause) -> Python figure scripts
REM  Toggle any step below (1 = run, 0 = skip) - e.g. relaunch only from
REM  harmonise onwards after a fix, or enable the upstream steps for a full
REM  from-scratch rebuild. The chain STOPS at the first error.
REM
REM  Usage:  double-click, or from any prompt:   run_pipeline.bat
REM          log to a file:                      run_pipeline.bat ^> run.log 2^>^&1
REM ===========================================================================
setlocal
set "ROOT=%~dp0"

REM ---- step toggles ---------------------------------------------------------
set RUN_PREP_EDGAR=0
set RUN_FFMAR=0
set RUN_CROP=1
set RUN_GRAZING=0
set RUN_NH3=1
set RUN_NOX=1
set RUN_HARMONISE=1
set RUN_NLEACH_TABLES=1
set RUN_SATELLITES=1
set RUN_ANCHORED=1
set RUN_E1_PAUSE=1
set RUN_FIGURES_PY=1

REM ---- conda installation (edit if yours is elsewhere) -------------------------
if not defined CONDA_ROOT set "CONDA_ROOT=%USERPROFILE%\AppData\Local\anaconda3"

REM ---- activate the geo2 conda environment ---------------------------------
call "%CONDA_ROOT%\Scripts\activate.bat" geo2
if errorlevel 1 (
  echo [ERROR] could not activate conda env geo2 - open an Anaconda Prompt
  echo         and run this .bat from there.
  goto :fail
)

if "%RUN_PREP_EDGAR%"=="1" (
  call :step "%ROOT%." 0_prepare_EDGAR_emissions.py
  if errorlevel 1 goto :fail
)
if "%RUN_FFMAR%"=="1" (
  call :step "%ROOT%A_agricultural_leaching\3. CFs" c_make_FFmar_XF_basin.py
  if errorlevel 1 goto :fail
)
if "%RUN_CROP%"=="1" (
  call :step "%ROOT%A_agricultural_leaching" 1_crop_eutrophication_pipeline.py
  if errorlevel 1 goto :fail
)
if "%RUN_GRAZING%"=="1" (
  call :step "%ROOT%A_agricultural_leaching" 2_grazing_eutrophication_pipeline.py
  if errorlevel 1 goto :fail
)
if "%RUN_NH3%"=="1" (
  call :step "%ROOT%B_airborne_NH3" 1_apply_NH3_CF_country_LME.py
  if errorlevel 1 goto :fail
)
if "%RUN_NOX%"=="1" (
  call :step "%ROOT%C_airborne_NOx" 1_apply_NOx_CF_country_LME.py
  if errorlevel 1 goto :fail
)
if "%RUN_HARMONISE%"=="1" (
  call :step "%ROOT%D_Final_Database" 0_harmonise_pathways.py
  if errorlevel 1 goto :fail
)
if "%RUN_NLEACH_TABLES%"=="1" (
  call :step "%ROOT%D_Final_Database" 1_Nleaching_country_tables.py
  if errorlevel 1 goto :fail
)
if "%RUN_SATELLITES%"=="1" (
  call :step "%ROOT%E_MRIO_GLORIA_Satellites" 0_build_MRIO_satellites.py
  if errorlevel 1 goto :fail
)
if "%RUN_ANCHORED%"=="1" (
  call :step "%ROOT%E_MRIO_GLORIA_Satellites" 1_check_GLORIA_vs_EEZ_emissions.py
  if errorlevel 1 goto :fail
  call :step "%ROOT%E_MRIO_GLORIA_Satellites" 2_make_anchored_satellites.py
  if errorlevel 1 goto :fail
  call :step "%ROOT%E_MRIO_GLORIA_Satellites" 3_PBA_before_after_table.py
  if errorlevel 1 goto :fail
)
if "%RUN_E1_PAUSE%"=="1" (
  echo.
  echo ===========================================================================
  echo  NOW RUN IN MATLAB:  F_Practical_case\E_1_Consumption_eutrophication_LME.m
  echo  twice - BATCH = 'original' and BATCH = 'anchored', years 2015-2022.
  echo  Press a key here when both runs are finished.
  echo ===========================================================================
  pause
)
if "%RUN_FIGURES_PY%"=="1" (
  call :step "%ROOT%F_Practical_case" F_5_sector_tables_from_satellite.py
  if errorlevel 1 goto :fail
  call :step "%ROOT%F_Practical_case" F_5_sector_tables_from_satellite.py anchored
  if errorlevel 1 goto :fail
  call :step "%ROOT%F_Practical_case" F_3_Figure1_map.py
  if errorlevel 1 goto :fail
  for %%Y in (2015 2016 2017 2018 2019 2020 2021 2022) do (
    call :step "%ROOT%F_Practical_case" F_4_Sankey_reef.py %%Y anchored
    if errorlevel 1 goto :fail
    call :step "%ROOT%F_Practical_case" F_6_build_database.py %%Y
    if errorlevel 1 goto :fail
  )
  echo.
  echo  Then run in R:  F_2_Figures_CBA_PBA.R  and  F_7_climate_sector_flow.R
  echo  and in node:    make_table1.js
)

echo.
echo ===========================================================================
echo  [%date% %time%]  ALL REQUESTED STEPS COMPLETED
echo  Check that every "verify" line of the satellite step printed OK.
echo ===========================================================================
pause
exit /b 0

:step
echo.
echo ===========================================================================
echo  [%date% %time%]  RUNNING  %~2
echo  in  %~1
echo ===========================================================================
cd /d "%~1"
if not exist "%~2" (
  echo [ERROR] script not found: %~2  (renamed? edit run_pipeline.bat^)
  exit /b 1
)
python "%~2" %3 %4
exit /b %errorlevel%

:fail
echo.
echo ===========================================================================
echo  [%date% %time%]  PIPELINE STOPPED on an error - see the message above.
echo  Fix it, set the already-finished steps to 0, and relaunch this .bat.
echo ===========================================================================
pause
exit /b 1
