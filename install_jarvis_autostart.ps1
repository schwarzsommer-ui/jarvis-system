param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "JARVIS Local Runtime"
$voiceTaskName = "JARVIS Voice Wake Listener"
$startScript = Join-Path $projectRoot "start_v2.ps1"
$python = if (Test-Path (Join-Path $projectRoot "venv\Scripts\python.exe")) {
    Join-Path $projectRoot "venv\Scripts\python.exe"
} else {
    (Get-Command python.exe -ErrorAction Stop).Source
}
$listener = Join-Path $projectRoot "voice_wake_listener.py"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $voiceTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "J.A.R.V.I.S.-Autostart entfernt."
    exit 0
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""
)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Days 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

$voiceAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "`"$listener`"" `
    -WorkingDirectory $projectRoot
$voiceSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $voiceTaskName -Action $voiceAction -Trigger $trigger -Settings $voiceSettings -Force | Out-Null

Write-Host "J.A.R.V.I.S.-Autostart ist für Benutzer $env:USERNAME eingerichtet."
Write-Host "Wake-Listener startet bei der Anmeldung und wird bei Absturz neu gestartet."
