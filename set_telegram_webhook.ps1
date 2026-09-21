param(
    [Parameter(Mandatory = $true)]
    [string]$SiteUrl,
    [Parameter(Mandatory = $true)]
    [string]$Secret
)

$ErrorActionPreference = "Stop"
$envPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) ".env"
$lines = Get-Content $envPath
$tokenLine = $lines | Where-Object { $_ -match "^TELEGRAM_BOT_TOKEN=" } | Select-Object -First 1
if (-not $tokenLine) { throw "TELEGRAM_BOT_TOKEN fehlt in .env." }
$token = ($tokenLine -split "=", 2)[1].Trim()
if ([string]::IsNullOrWhiteSpace($token)) { throw "TELEGRAM_BOT_TOKEN ist leer." }

$webhook = $SiteUrl.TrimEnd("/") + "/.netlify/functions/telegram-webhook"
$uri = "https://api.telegram.org/bot$token/setWebhook"
$body = @{
    url = $webhook
    secret_token = $Secret
    allowed_updates = @("message")
} | ConvertTo-Json
$result = Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json" -Body $body
if (-not $result.ok) { throw "Telegram-WebHook konnte nicht gesetzt werden." }
Write-Host "Telegram-WebHook gesetzt: $webhook"
