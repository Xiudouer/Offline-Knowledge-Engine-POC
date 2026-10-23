$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    python -m PyInstaller --noconfirm --onedir --name OfflineKnowledgeEngine --paths . --exclude-module psycopg --exclude-module psycopg_binary --exclude-module numpy --exclude-module PIL --exclude-module cryptography --exclude-module Crypto --distpath build/dist --workpath build/work --specpath build run.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    & .\build\dist\OfflineKnowledgeEngine\OfflineKnowledgeEngine.exe demo
    if ($LASTEXITCODE -ne 0) { throw 'Frozen parser self-test failed' }
    python scripts/build_release.py --dist-dir build/dist/OfflineKnowledgeEngine
    if ($LASTEXITCODE -ne 0) { throw 'Offline release packaging failed' }
} finally { Pop-Location }
