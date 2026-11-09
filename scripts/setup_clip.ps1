$ErrorActionPreference = 'Stop'
Write-Host 'Installing CPU-only PyTorch and optional CLIP dependencies.'
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
python -m pip install -r requirements-optional-clip.txt
if ($LASTEXITCODE -ne 0) { throw 'CLIP dependency installation failed.' }
Write-Host 'CLIP dependencies installed. The first render downloads the CLIP model weights.'
Write-Host 'Keep AME_CLIP_ENABLED=true in .env to enable sampled-frame semantic ranking.'
