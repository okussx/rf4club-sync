$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "RF4Club Sync kuruluyor..." -ForegroundColor Cyan

function Find-Python {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) { return "py.exe" }
    return $null
}

$pythonCommand = Find-Python
if (-not $pythonCommand) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "Python bulunamadı ve Windows Paket Yöneticisi kullanılamıyor." -ForegroundColor Red
        Write-Host "Python 3.12 kurup SETUP.bat dosyasını yeniden çalıştır."
        Read-Host "Kapatmak için Enter"
        exit 1
    }
    Write-Host "Windows Paket Yöneticisi ile Python 3.12 kuruluyor..." -ForegroundColor Yellow
    & $winget.Source install --id Python.Python.3.12 --exact --scope user --accept-package-agreements --accept-source-agreements --silent
    $pythonCommand = Get-ChildItem "$env:LocalAppData\Programs\Python\Python312\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if (-not $pythonCommand) {
        $pythonCommand = Find-Python
    }
}

if (-not $pythonCommand) { throw "Python kurulumu bulunamadı." }

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    if ($pythonCommand -eq "py.exe") {
        & $pythonCommand -3.12 -m venv .venv
    } else {
        & $pythonCommand -m venv .venv
    }
}

Write-Host "RF4Club Sync bileşenleri hazırlanıyor..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --progress-bar off --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --progress-bar off -r requirements-logger.txt

$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
foreach ($folder in @($desktop, $startMenu)) {
    if (-not (Test-Path -LiteralPath $folder)) { continue }
    $shortcut = $shell.CreateShortcut((Join-Path $folder "RF4Club Sync.lnk"))
    $shortcut.TargetPath = (Join-Path $PSScriptRoot "START.bat")
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = "RF4Club yakalama ve oyuncu istatistiği senkronizasyonu"
    $shortcut.Save()
}

Write-Host "Kurulum tamamlandı." -ForegroundColor Green
Write-Host "Masaüstündeki RF4Club Sync kısayoluyla uygulamayı çalıştırabilirsin."
Read-Host "Kapatmak için Enter"
