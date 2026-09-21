param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $projectRoot ".env"

function Read-RequiredValue([string]$Prompt, [switch]$Secret) {
    if ($Secret) {
        $secure = Read-Host $Prompt -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
    return Read-Host $Prompt
}

function Set-EnvValue([string[]]$Lines, [string]$Name, [string]$Value) {
    $pattern = "^" + [regex]::Escape($Name) + "="
    $found = $false
    $result = foreach ($line in $Lines) {
        if ($line -match $pattern) {
            $found = $true
            "$Name=$Value"
        }
        else {
            $line
        }
    }
    if (-not $found) {
        $result += "$Name=$Value"
    }
    return $result
}

$token = Read-RequiredValue "Telegram Bot-Token (Eingabe wird nicht angezeigt)" -Secret
$chatId = Read-RequiredValue "Telegram Chat-ID"
if ([string]::IsNullOrWhiteSpace($token) -or [string]::IsNullOrWhiteSpace($chatId)) {
    throw "Bot-Token und Chat-ID sind erforderlich."
}

$lines = if (Test-Path $envPath) { @(Get-Content -Path $envPath) } else { @() }
$lines = Set-EnvValue $lines "TELEGRAM_BOT_TOKEN" $token
$lines = Set-EnvValue $lines "TELEGRAM_CHAT_ID" $chatId
Set-Content -Path $envPath -Value $lines -Encoding UTF8
Write-Host "Telegram-Konfiguration wurde lokal gespeichert. Werte wurden nicht ausgegeben."
