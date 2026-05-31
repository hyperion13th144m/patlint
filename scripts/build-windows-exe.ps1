$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

python -m pip install --upgrade pip
python -m pip install -e ".[exe]"
python -m PyInstaller --clean patent-checker-api.spec

Write-Host "Built: dist\patent-checker-api.exe"
