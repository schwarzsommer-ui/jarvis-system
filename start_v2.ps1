param([switch]$CheckOnly)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$Python = if (Test-Path (Join-Path $ProjectRoot "venv\Scripts\python.exe")) {
    (Join-Path $ProjectRoot "venv\Scripts\python.exe")
} else {
    "python"
}

function Remove-StaleProjectProcesses {
    $portProcesses = @{}
    foreach ($connection in @(Get-NetTCPConnection -LocalPort 8000,8787 -State Listen -ErrorAction SilentlyContinue)) {
        if ($connection.OwningProcess) {
            $portProcesses[$connection.OwningProcess] = $true
        }
    }

    foreach ($processId in $portProcesses.Keys) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        $commandLine = [string]$process.CommandLine
        if ($commandLine -and $commandLine.Contains($ProjectRoot) -and $commandLine -match 'backend\.run_server|http\.server 8000') {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    $commandMatches = Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine.Contains($ProjectRoot) -and
            (
                $_.CommandLine -match 'backend\.run_server' -or
                $_.CommandLine -match 'http\.server 8000' -or
                $_.CommandLine -match '\\.executor\\\\.*' -or
                $_.CommandLine -match 'voice_wake_listener\.py'
            )
        }

    foreach ($process in $commandMatches | Sort-Object ProcessId) {
        if ($process.ProcessId -ne $PID) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

$pythonFiles = @(
    Get-ChildItem -Path ".\backend" -Filter "*.py" -File -Recurse |
        Select-Object -ExpandProperty FullName
    (Join-Path $ProjectRoot "voice_wake_listener.py")
)
& $Python -B -m py_compile $pythonFiles
if ($LASTEXITCODE -ne 0) { throw "V2-Syntaxcheck fehlgeschlagen." }
if ($CheckOnly) { Write-Host "J.A.R.V.I.S. V2 ist syntaktisch gültig."; exit 0 }

Remove-StaleProjectProcesses

if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $Python `
        -ArgumentList @("-m", "http.server", "8000", "--bind", "127.0.0.1") `
        -WorkingDirectory (Join-Path $ProjectRoot "frontend\dashboard") `
        -WindowStyle Hidden
}

foreach ($executor in @("python_executor.py", "browser_executor.py", "desktop_executor.py", "workflow_executor.py")) {
    if (-not (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*$executor*" -and $_.CommandLine.Contains($ProjectRoot) })) {
        Start-Process -FilePath $Python `
            -ArgumentList @(".\executor\$executor") `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Hidden
    }
}

if (-not (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $Python `
        -ArgumentList @("-m", "backend.run_server") `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden
}
