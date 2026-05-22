@echo off
rem =====================================================================
rem ok-wuthering-waves quick dev build
rem ---------------------------------------------------------------------
rem  Usage:
rem    build.bat              -- dev build: ensure venv, install deps,
rem                              build cython if any, smoke-test imports,
rem                              print absolute exe paths.
rem    build.bat --clean      -- delete .venv first, then full rebuild.
rem    build.bat --no-mobile  -- skip the mobile plugin smoke test.
rem    build.bat --portable   -- after dev build, also produce a self-
rem                              contained folder at dist\ok-ww-portable\
rem                              (Python + deps + project + run.bat).
rem    build.bat --help       -- show this help.
rem
rem  Python 3.12 sourcing order (first hit wins):
rem    1. existing .venv\Scripts\python.exe         (already built)
rem    2. .python\python.exe                        (portable, project-local)
rem    3. py -3.12 / python on PATH                 (system install)
rem    4. download portable Python 3.12.13 from python-build-standalone
rem       and unpack into .python\                  (~38 MB)
rem
rem  This is a *dev* build. The reported "executable" is the project's
rem  .venv\Scripts\python.exe -- launch the app via that interpreter
rem  + main.py / main_debug.py / main_mobile.py.
rem
rem  For a distributable .exe (China/Global setup.exe), push a tag like
rem  v0.1.0 -- the GitHub Actions workflow .github\workflows\build.yml
rem  will produce signed setup.exe artifacts. Local Tauri-based pyappify
rem  builds are heavyweight (Rust toolchain) and not done by this script.
rem =====================================================================

setlocal enabledelayedexpansion

rem -- arg parsing --------------------------------------------------------

set "DO_CLEAN=0"
set "DO_MOBILE=1"
set "DO_PORTABLE=0"
set "ARG=%~1"
:argloop
if "%ARG%"=="" goto :args_done
if /I "%ARG%"=="--help"      goto :help
if /I "%ARG%"=="-h"          goto :help
if /I "%ARG%"=="/?"          goto :help
if /I "%ARG%"=="--clean"     set "DO_CLEAN=1" & goto :next_arg
if /I "%ARG%"=="--no-mobile" set "DO_MOBILE=0" & goto :next_arg
if /I "%ARG%"=="--portable"  set "DO_PORTABLE=1" & goto :next_arg
echo [build] Unknown argument: %ARG%
goto :help
:next_arg
shift
set "ARG=%~1"
goto :argloop
:args_done

rem -- paths --------------------------------------------------------------

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV_DIR=%ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "LOCAL_PY_DIR=%ROOT%\.python"
set "LOCAL_PY_EXE=%LOCAL_PY_DIR%\python.exe"

rem Where to fetch a portable Python 3.12 from. Override via env var if
rem you want a different version. The "install_only" tarball is a full
rem standalone Python with pip already wired up.
if not defined PORTABLE_PYTHON_URL (
    set "PORTABLE_PYTHON_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20260510/cpython-3.12.13+20260510-x86_64-pc-windows-msvc-install_only.tar.gz"
)
set "PORTABLE_PYTHON_TAR=%ROOT%\.python.tar.gz"

if not exist "%ROOT%\main.py" (
    echo [build] ERROR: main.py not found at "%ROOT%".
    echo         Run build.bat from the ok-wuthering-waves project root.
    exit /b 1
)

rem -- clean? -------------------------------------------------------------

if "%DO_CLEAN%"=="1" (
    if exist "%VENV_DIR%" (
        echo [build] Removing existing %VENV_DIR% ...
        rmdir /s /q "%VENV_DIR%"
    )
)

rem -- ensure a Python 3.12 is available, somehow --------------------------
rem
rem We try, in order:
rem   1. existing .venv (use as-is)
rem   2. local portable .python\python.exe
rem   3. system py -3.12 launcher
rem   4. download a portable Python 3.12 into .python\

if exist "%VENV_PYTHON%" goto :venv_ready

set "BASE_PY="

if exist "%LOCAL_PY_EXE%" (
    set "BASE_PY=%LOCAL_PY_EXE%"
    echo [build] Found portable Python at "%LOCAL_PY_EXE%".
    goto :have_base_py
)

where py >nul 2>nul
if !errorlevel!==0 (
    py -3.12 -c "import sys" >nul 2>nul
    if !errorlevel!==0 (
        set "BASE_PY=py -3.12"
        echo [build] Found system Python 3.12 via py launcher.
        goto :have_base_py
    )
)

echo [build] No Python 3.12 found locally; downloading a portable copy ^(~38 MB^).
echo [build]   from: !PORTABLE_PYTHON_URL!
echo [build]   to  : %LOCAL_PY_DIR%
call :download_portable_python || goto :fail
set "BASE_PY=%LOCAL_PY_EXE%"

:have_base_py
echo [build] Creating .venv with %BASE_PY% ...
%BASE_PY% -m venv "%VENV_DIR%"
if not exist "%VENV_PYTHON%" (
    echo [build] ERROR: failed to create venv at "%VENV_DIR%".
    goto :fail
)

:venv_ready

rem -- pip install --------------------------------------------------------

echo [build] Upgrading pip ...
"%VENV_PYTHON%" -m pip install --quiet --upgrade pip
if errorlevel 1 goto :fail

echo [build] Installing requirements.txt ...
"%VENV_PYTHON%" -m pip install --quiet -r "%ROOT%\requirements.txt"
if errorlevel 1 goto :fail

if exist "%ROOT%\requirements-dev.txt" (
    echo [build] Installing requirements-dev.txt ...
    "%VENV_PYTHON%" -m pip install --quiet -r "%ROOT%\requirements-dev.txt"
)

if "%DO_MOBILE%"=="1" if exist "%ROOT%\plugins\mumu12" (
    echo [build] Installing mobile plugin extras ^(adbutils for minitouch^) ...
    "%VENV_PYTHON%" -m pip install --quiet adbutils
)

rem -- cython build_ext if .pyx files exist ------------------------------

set "HAS_PYX=0"
"%VENV_PYTHON%" -c "import glob,sys; sys.exit(0 if glob.glob('src/**/*.pyx', recursive=True) else 1)" 2>nul
if !errorlevel!==0 set "HAS_PYX=1"

if "%HAS_PYX%"=="1" (
    echo [build] Cython sources detected; building extensions in-place ...
    "%VENV_PYTHON%" "%ROOT%\setup.py" build_ext --inplace 1>nul
    if errorlevel 1 goto :fail
)

rem -- smoke tests --------------------------------------------------------

echo [build] Smoke test: importing config ...
"%VENV_PYTHON%" -c "from config import config; assert 'onetime_tasks' in config; print('  PC config OK,', len(config.get('onetime_tasks',[])), 'onetime +', len(config.get('trigger_tasks',[])), 'trigger tasks')"
if errorlevel 1 (
    echo [build] WARNING: PC config import failed. Some deps may be missing.
)

if "%DO_MOBILE%"=="1" if exist "%ROOT%\plugins\mumu12\__init__.py" (
    echo [build] Smoke test: importing plugins.mumu12 ...
    "%VENV_PYTHON%" -c "from config import config; from plugins.mumu12 import apply_to; cfg=apply_to(config); print('  mobile plugin OK,', len(cfg.get('onetime_tasks',[])) + len(cfg.get('trigger_tasks',[])), 'tasks after wrapping')"
    if errorlevel 1 (
        echo [build] WARNING: mobile plugin import failed -- check the traceback above.
    )
)

rem -- final report -------------------------------------------------------

echo.
echo ====================================================================
echo  BUILD OK
echo ====================================================================
echo  Interpreter (the "executable"):
echo    %VENV_PYTHON%
echo.
echo  Entry points:
echo    PC release :  %ROOT%\main.py
echo    PC debug   :  %ROOT%\main_debug.py
if exist "%ROOT%\main_mobile.py" (
    echo    Mobile     :  %ROOT%\main_mobile.py
)
echo.
echo  To launch:
echo    "%VENV_PYTHON%" "%ROOT%\main.py"
if exist "%ROOT%\main_mobile.py" (
    echo    "%VENV_PYTHON%" "%ROOT%\main_mobile.py"
)
echo.
echo  For a distributable setup.exe (signed, Tauri-built), push a tag
echo  like v0.1.0 -- GitHub Actions will run .github\workflows\build.yml.
echo ====================================================================

rem -- portable bundle (optional) -----------------------------------------

if "%DO_PORTABLE%"=="1" (
    call :portable_build
    if errorlevel 1 goto :fail
)

endlocal
exit /b 0

rem -- subroutines --------------------------------------------------------

:portable_build
rem Build a self-contained, redistributable folder at dist\ok-ww-portable\.
rem
rem Layout:
rem   dist\ok-ww-portable\
rem     python\          <- standalone Python 3.12 + installed deps
rem     src\             <- project source
rem     plugins\
rem     i18n\
rem     assets\
rem     ...
rem     main*.py / config.py / icon.* / LICENSE.txt
rem     run.bat / run_debug.bat / run_mobile.bat   (auto-generated)
rem
rem The folder works on any Windows 10+ machine; no Python install needed.

echo.
echo ====================================================================
echo  Building portable bundle ...
echo ====================================================================
set "PORTABLE_DIR=%ROOT%\dist\ok-ww-portable"
set "PORTABLE_PY=%PORTABLE_DIR%\python\python.exe"

rem 1. Make sure we have a portable Python source.
if not exist "%LOCAL_PY_EXE%" (
    echo [portable] No .python\ found; downloading first ...
    call :download_portable_python
    if errorlevel 1 exit /b 1
)

rem 2. Wipe previous bundle.
if exist "%PORTABLE_DIR%" (
    echo [portable] Removing previous bundle at %PORTABLE_DIR% ...
    rmdir /s /q "%PORTABLE_DIR%"
)
mkdir "%PORTABLE_DIR%" 2>nul
mkdir "%PORTABLE_DIR%\python" 2>nul

rem 3. Copy the Python runtime into bundle\python\.
echo [portable] Copying Python runtime ...
robocopy "%LOCAL_PY_DIR%" "%PORTABLE_DIR%\python" /E /NFL /NDL /NJH /NJS /NS /NP /NC >nul
if errorlevel 8 (
    echo [portable] ERROR: copying Python runtime failed.
    exit /b 1
)

rem 4. Install runtime deps INTO the bundled Python (not .venv).
echo [portable] Installing dependencies into bundle ^(this takes a few minutes^) ...
"%PORTABLE_PY%" -m pip install --upgrade --quiet pip
if errorlevel 1 exit /b 1
"%PORTABLE_PY%" -m pip install --quiet -r "%ROOT%\requirements.txt"
if errorlevel 1 exit /b 1
if "%DO_MOBILE%"=="1" if exist "%ROOT%\plugins\mumu12" (
    echo [portable] Installing mobile plugin extras ^(adbutils^) ...
    "%PORTABLE_PY%" -m pip install --quiet adbutils
)

rem 5. Copy project files.  Black-list approach so new top-level dirs
rem    are picked up automatically; excluded paths are dev-only or huge.
echo [portable] Copying project files ...
robocopy "%ROOT%" "%PORTABLE_DIR%" /E /NFL /NDL /NJH /NJS /NS /NP /NC ^
    /XD .git .venv .python dist ok_templates logs configs screenshots cache working updates build develop-eggs eggs sdist wheels share .pytest_cache .vscode .idea __pycache__ ^
    /XF *.pyc *.pyo *.pyx *.cpp *.so *.bat *.tar.gz pip-log.txt thread_dumps.txt md5.txt >nul
if errorlevel 8 (
    echo [portable] ERROR: copying project files failed.
    exit /b 1
)

rem 6. Generate launcher .bat files inside the bundle.
echo [portable] Writing launcher scripts ...
> "%PORTABLE_DIR%\run.bat" echo @echo off
>> "%PORTABLE_DIR%\run.bat" echo cd /d "%%~dp0"
>> "%PORTABLE_DIR%\run.bat" echo .\python\python.exe main.py %%*

if exist "%ROOT%\main_debug.py" (
    > "%PORTABLE_DIR%\run_debug.bat" echo @echo off
    >> "%PORTABLE_DIR%\run_debug.bat" echo cd /d "%%~dp0"
    >> "%PORTABLE_DIR%\run_debug.bat" echo .\python\python.exe main_debug.py %%*
)

if exist "%ROOT%\main_mobile.py" (
    > "%PORTABLE_DIR%\run_mobile.bat" echo @echo off
    >> "%PORTABLE_DIR%\run_mobile.bat" echo cd /d "%%~dp0"
    >> "%PORTABLE_DIR%\run_mobile.bat" echo .\python\python.exe main_mobile.py %%*
)

rem 7. Report size and paths.
set "PORTABLE_MB="
for /f %%S in ('powershell -NoProfile -Command "[math]::Round((Get-ChildItem -LiteralPath '%PORTABLE_DIR%' -Recurse -File ^| Measure-Object -Property Length -Sum).Sum / 1MB)" 2^>nul') do set "PORTABLE_MB=%%S"

echo.
echo ====================================================================
echo  PORTABLE BUNDLE READY
echo ====================================================================
echo  Folder:  %PORTABLE_DIR%
if defined PORTABLE_MB echo  Size  :  %PORTABLE_MB% MB
echo.
echo  Launchers:
echo    %PORTABLE_DIR%\run.bat
if exist "%PORTABLE_DIR%\run_debug.bat"  echo    %PORTABLE_DIR%\run_debug.bat
if exist "%PORTABLE_DIR%\run_mobile.bat" echo    %PORTABLE_DIR%\run_mobile.bat
echo.
echo  Zip the folder to redistribute.  Users can run it on any Windows
echo  10+ machine by double-clicking run.bat -- no Python install needed.
echo ====================================================================
exit /b 0

:download_portable_python
rem Download + extract a standalone Python 3.12 into %LOCAL_PY_DIR%.
rem Returns errorlevel 0 on success, non-zero on failure.

if exist "%PORTABLE_PYTHON_TAR%" del "%PORTABLE_PYTHON_TAR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri $env:PORTABLE_PYTHON_URL -OutFile $env:PORTABLE_PYTHON_TAR -UseBasicParsing } catch { Write-Error $_.Exception.Message; exit 1 }"
if not exist "%PORTABLE_PYTHON_TAR%" (
    echo [build] ERROR: download failed.  Check internet access or set
    echo         PORTABLE_PYTHON_URL to a reachable mirror and retry.
    exit /b 1
)

if not exist "%LOCAL_PY_DIR%" mkdir "%LOCAL_PY_DIR%"

rem The install_only tarball ships everything inside a top-level "python\"
rem directory; --strip-components=1 hoists its contents into LOCAL_PY_DIR.
rem Windows 10+ ships bsdtar as tar.exe which understands gzip + strip.
where tar >nul 2>nul
if errorlevel 1 (
    echo [build] ERROR: 'tar' not found.  Need Windows 10 build 17063+ for
    echo         bundled bsdtar, or install GNU tar manually.
    exit /b 1
)

tar -xzf "%PORTABLE_PYTHON_TAR%" -C "%LOCAL_PY_DIR%" --strip-components=1
if errorlevel 1 (
    echo [build] ERROR: extraction failed.
    exit /b 1
)

del "%PORTABLE_PYTHON_TAR%" 2>nul

if not exist "%LOCAL_PY_EXE%" (
    echo [build] ERROR: %LOCAL_PY_EXE% missing after extraction.
    exit /b 1
)

echo [build] Portable Python ready: %LOCAL_PY_EXE%
exit /b 0

rem -- helpers ------------------------------------------------------------

:help
echo ok-wuthering-waves build.bat
echo.
echo Usage:
echo   build.bat              dev build: create .venv if missing, install
echo                          deps, smoke-test imports, print exe paths.
echo   build.bat --clean      remove .venv first, then full rebuild.
echo   build.bat --no-mobile  skip the mobile-plugin smoke test
echo                          (also skips installing adbutils).
echo   build.bat --portable   after dev build, also produce a redistribut-
echo                          able folder at dist\ok-ww-portable\
echo                          (Python + deps + project + run.bat).
echo   build.bat --help       show this help.
echo.
echo If Python 3.12 is not installed system-wide, build.bat will download
echo a portable copy (~38 MB) into .python\ on first run.  Override the
echo download URL with the PORTABLE_PYTHON_URL environment variable.
echo.
echo This is a *dev* build. The "executable" reported is
echo .venv\Scripts\python.exe -- launch the app with it + main.py /
echo main_debug.py / main_mobile.py.
echo.
echo For a distributable setup.exe, push a tag like v0.1.0 to trigger the
echo GitHub Actions workflow .github\workflows\build.yml (Tauri-based,
echo signed). Local Tauri builds are heavyweight and not handled here.
endlocal
exit /b 0

:fail
echo.
echo [build] FAILED -- see error above.
endlocal
exit /b 1
