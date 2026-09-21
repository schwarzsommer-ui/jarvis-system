param(
    [switch]$Install,
    [switch]$CheckOnly,
    [string]$OllamaModel = "llama3.1"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Find-Python {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        $python = Get-Command python -ErrorAction SilentlyContinue
    }
    if ($null -eq $python) {
        throw "Python 3.11 oder 3.12 wurde nicht gefunden. Aktiviere beim Setup 'Add Python to PATH'."
    }
    return $python.Source
}

$Python = Find-Python
$version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($version -notin @("3.11", "3.12")) {
    throw "Unterstützt werden Python 3.11 oder 3.12, gefunden wurde $version."
}

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    if (-not $Install) {
        throw "Die lokale venv fehlt. Starte zuerst .\setup_jarvis.ps1 -Install."
    }
    & $Python -m venv .\venv
}
$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"

if ($Install) {
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r .\requirements-jarvis.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Die Jarvis-Pakete konnten nicht installiert werden."
    }
    & $VenvPython -m pip install "crewai>=0.86.0"
    if ($LASTEXITCODE -ne 0) {
        throw "CrewAI konnte nicht installiert werden."
    }
    & $VenvPython -m pip install "autogen-agentchat>=0.4.0"
    if ($LASTEXITCODE -ne 0) {
        throw "AutoGen konnte nicht installiert werden."
    }
    & $VenvPython -m pip install "open-interpreter>=0.4.3"
    if ($LASTEXITCODE -ne 0) {
        throw "Open Interpreter konnte nicht installiert werden."
    }
    New-Item -ItemType Directory -Force ".\Logs" | Out-Null
    New-Item -ItemType Directory -Force ".\screenshots" | Out-Null
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($null -eq $ollama) {
    Write-Warning "Ollama fehlt. Installiere es über https://ollama.com/download und starte das Setup erneut."
} elseif ($Install) {
    & $ollama.Source pull $OllamaModel
}

& $VenvPython -B -m py_compile .\jarvis.py .\desktop_control.py
if ($LASTEXITCODE -ne 0) {
    throw "Der Syntaxcheck ist fehlgeschlagen."
}

Write-Host "J.A.R.V.I.S.-Setup geprüft: $ProjectRoot" -ForegroundColor Green
Write-Host "Venv: $VenvPython" -ForegroundColor DarkCyan
Write-Host "Start: .\venv\Scripts\Activate.ps1; python .\jarvis.py" -ForegroundColor DarkCyan
