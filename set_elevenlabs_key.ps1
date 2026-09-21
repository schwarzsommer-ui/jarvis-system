param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $projectRoot ".env"

$secureKey = Read-Host "ElevenLabs API-Key eingeben" -AsSecureString
$keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
}

if ([string]::IsNullOrWhiteSpace($key)) {
    throw "Kein API-Key eingegeben."
}

$lines = @()
if (Test-Path $envPath) {
    $lines = Get-Content -Path $envPath
}

$updated = $false
$result = foreach ($line in $lines) {
    if ($line -match "^ELEVENLABS_API_KEY=") {
        $updated = $true
        "ELEVENLABS_API_KEY=$key"
    }
    else {
        $line
    }
}
if (-not $updated) {
    $result += "ELEVENLABS_API_KEY=$key"
}

Set-Content -Path $envPath -Value $result -Encoding UTF8
Write-Host "ElevenLabs-Key lokal gespeichert. Der Wert wurde nicht ausgegeben."
