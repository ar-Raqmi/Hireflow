@echo off
setlocal EnableExtensions EnableDelayedExpansion
:: hireflow.bat - thin ONLINE client for the deployed Hireflow pipeline (Windows).
:: Double-click to run. It needs Python 3.10+ (python.org) and curl (built into
:: Windows 11). Prompts for resume + preferences, uploads to Cloud Run, streams
:: live agent progress, prints the full report, and exports result-demo.html
:: (full clickable report) + result-demo.json into the working dir. Nothing
:: computed locally.

set "BASE_URL=https://hireflow-backend-296941301245.us-central1.run.app"
if defined HIREFLOW_BASE_URL set "BASE_URL=%HIREFLOW_BASE_URL%"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

%PY% -c "import sys" >nul 2>nul || (
  echo [error] Python not found. Install from https://python.org and rerun.
  pause
  exit /b 1
)
where curl >nul 2>nul || (
  echo [error] curl not found. It ships with Windows 11 - check your PATH.
  pause
  exit /b 1
)

echo.
echo   hireflow-cli . online . %BASE_URL%
echo   (the pipeline runs on Cloud Run - nothing is computed locally)
echo.

:: --- 1. resume file ----
:askfile
set "RESUME="
set /p "RESUME=Resume path (absolute, e.g. C:\Users\You\resume.pdf): "
if "%RESUME%"=="" echo no file given - aborting & pause & exit /b 1
if not exist "%RESUME%" (
  echo   not found: %RESUME%
  goto askfile
)

:: --- 2. work type ----
set "WORK=any"
echo.
echo Work type:  1) Remote   2) Onsite   3) Hybrid   4) Anywhere (skip)
choice /c 1234 /n /m "Pick 1-4: "
if errorlevel 4 set "WORK=any"
if errorlevel 3 if not errorlevel 4 set "WORK=hybrid"
if errorlevel 2 if not errorlevel 3 set "WORK=onsite"
if errorlevel 1 if not errorlevel 2 set "WORK=remote"
echo work_type: %WORK%

:: --- 3. locations ----
set "LOCS="
set /p "LOCS=Preferred work locations (comma separated; blank = anywhere): "
if "%LOCS%"=="" (
  echo locations: anywhere
) else (
  echo locations: %LOCS%
)

:: --- 4. target roles ----
set "TARGET="
set /p "TARGET=Target roles (comma separated, blank = let the agent infer): "
if "%TARGET%"=="" echo target_roles: ^(infer from resume^)

echo.
echo Running Hireflow ... this may take several minutes.
echo.

:: --- run the shared cross-platform logic ----
%PY% "%~dp0hireflow_run.py" "%BASE_URL%" "%RESUME%" "%WORK%" "%LOCS%" "%TARGET%"
echo.
echo Done. Press any key to exit.
pause >nul
endlocal
