# Run from the project root in PowerShell:  .\scripts\setup-backend.ps1
Set-Location "$PSScriptRoot\..\backend"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created backend\.env - EDIT IT (database password + JWT_SECRET) before continuing." -ForegroundColor Yellow }
