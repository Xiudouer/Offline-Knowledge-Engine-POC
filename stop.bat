@echo off
cd /d "%~dp0"
if exist "OfflineKnowledgeEngine.exe" (
  OfflineKnowledgeEngine.exe stop
) else (
  python run.py stop
)
pause
