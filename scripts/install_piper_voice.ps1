$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$voiceDir = Join-Path $root "models\voices"
$model = Join-Path $voiceDir "de_DE-thorsten-medium.onnx"
$config = Join-Path $voiceDir "de_DE-thorsten-medium.onnx.json"
$base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium"

New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
python -m pip install piper-tts
Invoke-WebRequest -Uri "$base/de_DE-thorsten-medium.onnx" -OutFile $model
Invoke-WebRequest -Uri "$base/de_DE-thorsten-medium.onnx.json" -OutFile $config
Write-Host "Piper-Stimme installiert: $model"
