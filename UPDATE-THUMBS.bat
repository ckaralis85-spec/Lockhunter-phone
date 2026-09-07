@echo off
REM ===========================================================================
REM  Lock Hunter - UPDATE PHONE DATA (and push to GitHub)
REM
REM  Run this whenever you want the phone refreshed. It:
REM    1. pulls the latest from your phone repo,
REM    2. downloads any NEW or CHANGED lock thumbnails into thumbs\,
REM    3. mirrors your Owned + Wishlist to collection.json (so the hosted phone
REM       page can load your collection even when LPU's API is down),
REM    4. commits and pushes the changes to GitHub Pages.
REM
REM  Put this file, mirror_thumbs.py AND mirror_profile.py inside your cloned
REM  phone-repo folder - the one that has the hidden .git folder, index.html and
REM  the thumbs folder.
REM
REM  Usage:   double-click to run once
REM           UPDATE-THUMBS.bat /auto     no pause, for Windows Task Scheduler
REM
REM  The first push needs a one-time GitHub sign-in in your browser. After that
REM  Windows remembers it, so scheduled runs push on their own.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "RC=0"

set "NOPAUSE="
if /i "%~1"=="/auto" set "NOPAUSE=1"

if not exist ".git" goto :not_repo
if not exist "mirror_thumbs.py" goto :no_script

where git >nul 2>&1
if errorlevel 1 goto :no_git

set "PYEXE="
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if not defined PYEXE ( py -3 --version >nul 2>&1 && set "PYEXE=py -3" )
if not defined PYEXE ( py --version >nul 2>&1 && set "PYEXE=py" )
if not defined PYEXE ( python --version >nul 2>&1 && set "PYEXE=python" )
if not defined PYEXE ( python3 --version >nul 2>&1 && set "PYEXE=python3" )
if not defined PYEXE goto :no_python

echo.
echo  [1/4] Syncing with GitHub...
git pull --ff-only

echo.
echo  [2/4] Downloading new and changed thumbnails...
set "MIRROR_NO_PAUSE=1"
%PYEXE% "mirror_thumbs.py" --out "thumbs"
if errorlevel 1 goto :dl_failed

echo.
echo  [3/4] Mirroring your collection (and any compare targets)...
if exist "mirror_profile.py" (
    %PYEXE% "mirror_profile.py"
) else (
    echo  mirror_profile.py not found - skipping the collection mirror.
)

echo.
echo  [4/4] Publishing changes...
git add thumbs collection.json
if exist "collections" git add collections
git diff --cached --quiet && goto :nothing
git commit -m "Update mirrored thumbnails and collection"
git push
if errorlevel 1 goto :push_failed

echo.
echo ===========================================================================
echo  Done. Thumbnails and your collection were pushed to GitHub Pages.
echo ===========================================================================
goto :end

:nothing
echo.
echo  Nothing to publish - your phone data is already up to date.
goto :end

:not_repo
echo.
echo This must run from inside your cloned phone-repo folder - the one that has
echo a hidden .git folder plus index.html and thumbs. Copy this file,
echo mirror_thumbs.py and mirror_profile.py into that folder, then run it there.
echo You are in:
echo    %CD%
set "RC=1"
goto :end

:no_script
echo.
echo Could not find mirror_thumbs.py next to this file. Keep UPDATE-THUMBS.bat,
echo mirror_thumbs.py and mirror_profile.py together in the cloned repo folder.
set "RC=1"
goto :end

:no_git
echo.
echo Git was not found. Install it from git-scm.com or run:  winget install Git.Git
echo then open a new window and run this again.
set "RC=1"
goto :end

:no_python
echo.
echo No Python was found. Install Lock Hunter with "Install LockHunter.bat",
echo or install Python from python.org, and run this again.
set "RC=1"
goto :end

:dl_failed
echo.
echo The download step failed - see the messages above. Nothing was pushed.
set "RC=1"
goto :end

:push_failed
echo.
echo The push failed. If it mentions sign-in, complete the GitHub window and run
echo again. If it mentions "rejected" or "behind", open GitHub Desktop or run
echo "git pull" here first, then run this again.
set "RC=1"
goto :end

:end
if not defined NOPAUSE pause
exit /b %RC%
