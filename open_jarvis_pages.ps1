$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$pages = @(
    "file:///$($root -replace '\\', '/')/JarvisUI/index.html",
    "https://claude.ai/login",
    "https://www.make.com/en/login",
    "https://app.netlify.com/login",
    "https://www.tradingview.com/accounts/signin/",
    "https://web.telegram.org"
)

foreach ($page in $pages) {
    Start-Process $page
    Start-Sleep -Milliseconds 250
}

Write-Host "JARVIS-Arbeitsseiten wurden geöffnet." -ForegroundColor Cyan
