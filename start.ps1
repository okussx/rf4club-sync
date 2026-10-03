$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:RF4CLUB_API_URL = if ($env:RF4CLUB_API_URL) { $env:RF4CLUB_API_URL } else { "https://rf4club.com" }

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    Write-Host "İlk kurulum başlatılıyor..." -ForegroundColor Cyan
    & "$PSScriptRoot\install.ps1"
}

$arguments = @("rf4club_sync.py")

$dataRoot = if ($env:RF4CLUB_DATA_DIR) { $env:RF4CLUB_DATA_DIR } else { Join-Path $env:LOCALAPPDATA "RF4Club Sync" }
$deviceFile = Join-Path $dataRoot "device.json"
if (-not (Test-Path -LiteralPath $deviceFile) -and -not (Test-Path -LiteralPath ".rf4club-device.json")) {
    Write-Host "RF4Club profilinden bir eşleştirme kodu oluştur." -ForegroundColor Yellow
    $pairingCode = Read-Host "8 karakterli eşleştirme kodu"
    if (-not [string]::IsNullOrWhiteSpace($pairingCode)) {
        $arguments += @("--pair", $pairingCode.Trim())
    }
}

& ".\.venv\Scripts\python.exe" @arguments

if ($LASTEXITCODE -ne 0) {
    Write-Host "RF4Club Sync hata koduyla kapandı: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Kapatmak için Enter"
}
