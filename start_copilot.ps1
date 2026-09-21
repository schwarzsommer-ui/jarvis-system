param(
    [string]$Model = "qwen2.5:14b"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($null -eq $ollama) {
    throw "Ollama wurde nicht gefunden. Installiere Ollama kostenlos von https://ollama.com."
}

$env:JARVIS_PROVIDER = "ollama"
$env:OLLAMA_MODEL = $Model
$env:OLLAMA_LLM_LIBRARY = "cpu"
$env:OLLAMA_NO_CUDA = "1"
$env:OLLAMA_HOST = "127.0.0.1:11434"

try {
    Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
} catch {
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
        }
    }
    if (-not $ready) {
        throw "Ollama konnte nicht gestartet werden."
    }
}

Write-Host "Kostenloser lokaler Copilot startet mit Ollama: $Model" -ForegroundColor Cyan
Start-Process -FilePath "py" -ArgumentList "-B", ".\local_copilot_server.py" -WindowStyle Hidden
& py -B ".\main.py"
if ($LASTEXITCODE -ne 0) {
    throw "J.A.R.V.I.S. wurde mit Fehlercode $LASTEXITCODE beendet."
}
