$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 1) Build the app EXE (dist\AgentForge.exe)
& "$PSScriptRoot\build_exe.ps1"
if ($LASTEXITCODE -ne 0) { throw "AgentForge.exe build failed" }

# 2) Locate the Inno Setup 6 compiler
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}
if (-not $iscc) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php"
}

# 3) Compile the end-user installer (dist\installer\AgentForge-Setup.exe)
Write-Host "==> Compiling installer with Inno Setup..."
& $iscc "installer\AgentForge.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }

# 4) The installer bundles the app, so remove the raw portable EXE — the final
#    deliverable is just the Setup installer.
Remove-Item -LiteralPath "dist\AgentForge.exe" -Force

Write-Host "`nDone! End users can now download and run:"
Write-Host "  dist\installer\AgentForge-Setup.exe"