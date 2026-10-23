@echo off
cd /d "%~dp0"
if exist "OfflineKnowledgeEngine.exe" (
  OfflineKnowledgeEngine.exe demo
) else (
  python run.py demo
)
echo.
pause
