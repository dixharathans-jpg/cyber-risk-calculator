@echo off
REM Double-click this file to rebuild the risk report from data\sample_register.csv
REM It creates reports\risk_report.html and reports\risk_report.pdf
cd /d "%~dp0"

python assess.py
if errorlevel 1 goto :error

REM --- Make the PDF with Microsoft Edge (installed on every Windows 11 PC) ---
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" goto :nopdf

if exist "reports\risk_report.pdf" del "reports\risk_report.pdf"
echo Creating PDF...
"%EDGE%" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf-no-header --print-to-pdf="%CD%\reports\risk_report.pdf" "%CD%\reports\risk_report.html"
if not exist "reports\risk_report.pdf" goto :nopdf

echo PDF report : reports\risk_report.pdf
start "" "reports\risk_report.pdf"
exit /b

:nopdf
echo Could not create the PDF automatically.
echo Opening the HTML report instead: press Ctrl + P and choose "Save as PDF".
start "" "reports\risk_report.html"
pause
exit /b

:error
echo.
echo Something went wrong. Read the error above, fix the CSV, then try again.
pause
