$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Önce SETUP.bat ile geliştirme ortamını hazırla."
}

Write-Host "RF4Club Sync Windows paketi hazırlanıyor..." -ForegroundColor Cyan
& $python -m pip install --disable-pip-version-check --progress-bar off "pyinstaller>=6.16,<7"

# PyInstaller intentionally refuses to run with C:\Windows in its current
# working path. This repository happens to live below that directory, so stage
# only the build inputs in the user's temporary directory.
$stage = Join-Path $env:TEMP ("rf4club-sync-build-" + [guid]::NewGuid().ToString("N"))
$stageDist = Join-Path $stage "dist"
$stageWork = Join-Path $stage "build"
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "rf4club-sync.spec") -Destination $stage
Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.py" -File | Copy-Item -Destination $stage
Push-Location $stage
try {
    & $python -m PyInstaller --noconfirm --clean --distpath $stageDist --workpath $stageWork "rf4club-sync.spec"
} finally {
    Pop-Location
}

$packagedApp = Join-Path $stageDist "RF4Club Sync"
if (-not (Test-Path -LiteralPath $packagedApp)) { throw "Paketlenmiş uygulama üretilemedi." }

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $knownPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $knownPath) { $iscc = Get-Item $knownPath }
}
if (-not $iscc) {
    $knownPath = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $knownPath) { $iscc = Get-Item $knownPath }
}
if (-not $iscc) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "Setup oluşturucu hazırlanıyor..." -ForegroundColor Cyan
        & $winget.Source install --id JRSoftware.InnoSetup --exact --accept-package-agreements --accept-source-agreements --silent
        $knownPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $knownPath) { $iscc = Get-Item $knownPath }
        if (-not $iscc) {
            $knownPath = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
            if (Test-Path -LiteralPath $knownPath) { $iscc = Get-Item $knownPath }
        }
    }
}
if (-not $iscc) {
    throw "Inno Setup 6 bulunamadı. dist\RF4Club Sync klasörü hazır, ancak Setup.exe üretilemedi."
}

$isccPath = if ($iscc -is [System.Management.Automation.CommandInfo]) { $iscc.Source } else { $iscc.FullName }
& $isccPath "/DSourceDir=$packagedApp" "installer.iss"
Write-Host "Hazır: release\RF4Club-Sync-Setup.exe" -ForegroundColor Green
