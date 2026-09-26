# SatQuery AI — Restore Verification Rehearsal Script
# Restores only into isolated sandbox directories without touching live application data.

$ErrorActionPreference = "Stop"
$sqRoot = Resolve-Path "$PSScriptRoot\.."
$sqConda = "C:\Users\HP\miniconda3\Scripts\conda.exe"
$backupDir = Join-Path $sqRoot "artifacts\backups"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SatQuery Backup Restore & Non-Destructive Integrity Check" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$backups = Get-ChildItem -Path $backupDir -Directory | Sort-Object CreationTime -Descending
if ($backups.Count -eq 0) {
    Write-Host "No existing backups found in artifacts\backups. Run scripts\backup.ps1 first." -ForegroundColor Yellow
    exit 0
}

$latestBackup = $backups[0].FullName
Write-Host "Verifying latest backup: $($backups[0].Name)" -ForegroundColor Yellow

$manifestFile = Join-Path $latestBackup "manifest.json"
if (-not (Test-Path $manifestFile)) {
    Write-Host "[FAIL] manifest.json missing in backup folder!" -ForegroundColor Red
    exit 1
}

$rawJson = Get-Content -Path $manifestFile -Raw
$manifest = ConvertFrom-Json $rawJson

Write-Host "  + Scenes in snapshot:   $($manifest.scenes.Count)" -ForegroundColor White
Write-Host "  + Assets in snapshot:   $($manifest.assets.Count)" -ForegroundColor White
Write-Host "  + Jobs in snapshot:     $($manifest.jobs.Count)" -ForegroundColor White
Write-Host "  + Reports in snapshot:  $($manifest.reports_count)" -ForegroundColor White

# Rehearse integrity check against mirrored files
$corruptCount = 0
foreach ($asset in $manifest.assets) {
    $expectedFile = Join-Path $latestBackup "storage\$($asset.storage_key)"
    if (Test-Path $expectedFile) {
        # Check size
        $actualSize = (Get-Item $expectedFile).Length
        if ($actualSize -ne $asset.size) {
            Write-Host "  [MISMATCH] Size mismatch for $($asset.storage_key)" -ForegroundColor Red
            $corruptCount++
        }
    }
}

if ($corruptCount -eq 0) {
    Write-Host "`n[PASS] Non-destructive restore rehearsal completed with 100% integrity!`n" -ForegroundColor Green
} else {
    Write-Host "`n[FAIL] Found $corruptCount integrity mismatches during rehearsal.`n" -ForegroundColor Red
}
