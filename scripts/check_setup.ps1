py --version
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 4 }
catch { Write-Warning "Ollama not running. Install Ollama, then run: ollama pull qwen2.5:3b" }
node --version
