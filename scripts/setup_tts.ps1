$ErrorActionPreference = "Stop"
$VoiceDir = Join-Path $PSScriptRoot "..\models\voices"
New-Item -ItemType Directory -Force -Path $VoiceDir | Out-Null

Write-Host "Installing Piper TTS..."
python -m pip install --upgrade piper-tts

Write-Host "Downloading the English US Ryan high-quality voice..."
python -m piper.download_voices --data-dir $VoiceDir en_US-ryan-high

$Model = Join-Path $VoiceDir "en_US-ryan-high.onnx"
if (-not (Test-Path $Model)) {
    throw "Piper voice download did not create $Model. Check the available voice list at https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md"
}
Write-Host "Piper is ready: $Model"
