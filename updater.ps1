# Grecovery Auto-Updater

$repoOwner  = "thayeeb9211"
$repoName   = "Grecovery"
$versionUrl = "https://raw.githubusercontent.com/$repoOwner/$repoName/main/version.txt"
$zipUrl     = "https://github.com/$repoOwner/$repoName/archive/refs/heads/main.zip"
$localFile  = Join-Path $PSScriptRoot "version.txt"

$localVer = "0.0.0"
if (Test-Path $localFile) { $localVer = (Get-Content $localFile -Raw).Trim() }

try {
    $remoteVer = (Invoke-WebRequest -Uri $versionUrl -UseBasicParsing -TimeoutSec 6).Content.Trim()

    if ($remoteVer -ne $localVer) {
        Write-Host ""
        Write-Host "  +----------------------------------------------------+" -ForegroundColor Cyan
        Write-Host "  |  NEW VERSION FOUND: v$remoteVer                     " -ForegroundColor Cyan
        Write-Host "  |  Downloading update, please wait...                 " -ForegroundColor Cyan
        Write-Host "  +----------------------------------------------------+" -ForegroundColor Cyan
        Write-Host ""

        $tmpZip = Join-Path $env:TEMP "grecovery_update.zip"
        $tmpDir = Join-Path $env:TEMP "grecovery_update"

        Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
        if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
        Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

        $extracted = Join-Path $tmpDir "$repoName-main"
        Copy-Item -Path "$extracted\*" -Destination $PSScriptRoot -Recurse -Force

        Remove-Item $tmpZip  -Force -ErrorAction SilentlyContinue
        Remove-Item $tmpDir  -Recurse -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "  +----------------------------------------------------+" -ForegroundColor Green
        Write-Host "  |  Gateway Recovery Project is up to date! (v$remoteVer)" -ForegroundColor Green
        Write-Host "  +----------------------------------------------------+" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "  Gateway Recovery Project is up to date. (v$localVer)" -ForegroundColor Green
    }
} catch {
    Write-Host "  (Update check skipped - no internet connection)" -ForegroundColor DarkGray
}
