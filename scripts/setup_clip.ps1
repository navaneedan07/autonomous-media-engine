$ErrorActionPreference = 'Stop'
Write-Host 'Installing optional CPU CLIP dependencies. This can download several GB.'
python -m pip install -r requirements-optional-clip.txt
if ($LASTEXITCODE -ne 0) { throw 'CLIP dependency installation failed.' }
Write-Host 'CLIP dependencies installed. The first render downloads the CLIP model weights.'
Write-Host 'Set AME_CLIP_ENABLED=true in .env to enable sampled-frame semantic ranking.'
