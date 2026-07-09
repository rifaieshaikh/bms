@echo off
setlocal
cd /d "%~dp0\.."
set VAYBOOKS_DATA_DIR=%VAYBOOKS_DATA_DIR%
"%~dp0..\..\python\python.exe" -m vaybooks.bms.infrastructure.db.migrations.runner
endlocal
