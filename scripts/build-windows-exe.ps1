$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

python -m pip install --upgrade pip
python -m pip install -e ".[exe]"
python -m PyInstaller --clean patlint-api.spec

Write-Host "Built: dist\patlint-api.exe"
