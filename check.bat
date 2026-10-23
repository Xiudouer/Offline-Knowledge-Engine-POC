@echo off
cd /d "%~dp0"
if exist "OfflineKnowledgeEngine.exe" (
  OfflineKnowledgeEngine.exe check
) else (
  python run.py check
)
pause
