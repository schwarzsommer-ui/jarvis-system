$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $projectRoot ".env"

if (-not (Test-Path $envPath)) {
    throw "Die Datei .env wurde nicht gefunden."
}

$secureKey = Read-Host "OpenRouter-Schlüssel einfügen (Eingabe wird verborgen)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($key) -or $key -notmatch "^sk-or-") {
    throw "Der eingegebene Wert sieht nicht wie ein OpenRouter-Schlüssel aus."
}

$lines = @(Get-Content -Path $envPath)
$found = $false
$updated = foreach ($line in $lines) {
    if ($line -match "^OPENROUTER_API_KEY=") {
        $found = $true
        "OPENROUTER_API_KEY=$key"
    } else {
        $line
    }
}
if (-not $found) {
    $updated += "OPENROUTER_API_KEY=$key"
}
Set-Content -Path $envPath -Value $updated -Encoding utf8

Write-Host "OpenRouter-Schlüssel wurde lokal gespeichert."
Write-Host "Du kannst dieses Fenster jetzt schließen."
Read-Host "Enter zum Beenden"
