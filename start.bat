@echo off
cd /d "%~dp0"
if exist "OfflineKnowledgeEngine.exe" (
  OfflineKnowledgeEngine.exe start
) else (
  python run.py start
)
echo.
pause
