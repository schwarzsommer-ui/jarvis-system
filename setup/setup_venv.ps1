param([switch]$Install)
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".\venv\Scripts\python.exe")) { python -m venv .\venv }
if ($Install) {
  .\venv\Scripts\python.exe -m pip install -r .\setup\requirements_backend.txt
  .\venv\Scripts\python.exe -m pip install -r .\setup\requirements_executor.txt
}
Write-Host "Venv bereit. Aktivierung: .\venv\Scripts\Activate.ps1"
