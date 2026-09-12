$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "==> Generating icons..."
& $py "tools\make_icons.py"

Write-Host "==> Installing PyInstaller..."
& $py -m pip install pyinstaller --quiet

$data = @(
  "pg_ui;pg_ui",
  "prompt_generation;prompt_generation",
  "data;data",
  "requirements.txt;.",
  ".env.example;."
)

Write-Host "==> Building AgentForge.exe..."
& $py -m PyInstaller @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--noconsole",
  "--name", "AgentForge",
  "--icon", "pg_ui\static\favicon.ico",
  "--collect-all", "uvicorn",
  "--collect-all", "webview",
  "--hidden-import", "pg_ui.app",
  "--hidden-import", "prompt_generation.config",
  "--add-data", $data[0],
  "--add-data", $data[1],
  "--add-data", $data[2],
  "--add-data", $data[3],
  "--add-data", $data[4],
  "--exclude-module", "tkinter",
  "launch.py"
)
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "`nBuilt: dist\AgentForge.exe"
Write-Host "Tip: install Inno Setup 6 then compile installer\AgentForge.iss to produce AgentForge-Setup.exe"