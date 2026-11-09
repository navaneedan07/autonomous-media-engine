$ErrorActionPreference = 'Stop'
python -m pip install -r requirements-optional-alignment.txt
Write-Host 'Local word-level caption alignment installed. First render downloads the base.en model.'
