param(
    [switch]$SkipPayloadBuild,
    [switch]$SkipCompile,
    [string]$Compiler = '',
    [string]$BuildRoot = 'D:\YOLOStudio-CUDA-Build'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$Payload = Join-Path $BuildRoot 'payload'
$ReleaseDir = Join-Path $BuildRoot 'installer'
if (-not $Compiler) {
    $Compiler = @(
        (Join-Path $PSScriptRoot 'tmp\installer-tools\Inno Setup\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler) { throw 'Inno Setup compiler not found.' }
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not $SkipPayloadBuild) {
    & (Join-Path $PSScriptRoot 'build-launcher.ps1')
    & $Python (Join-Path $PSScriptRoot 'tools\fetch_cuda_wheels.py') --build-root $BuildRoot
    if ($LASTEXITCODE -ne 0) { throw 'CUDA wheel download or verification failed.' }
    & $Python (Join-Path $PSScriptRoot 'tools\build_auto_cuda.py') --build-root $BuildRoot --output $Payload --clean
    if ($LASTEXITCODE -ne 0) { throw 'Auto CUDA payload build failed.' }
}
$Info = Get-Content -LiteralPath (Join-Path $Payload 'distribution.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Info.profile -ne 'auto-cuda') { throw 'Expected an auto-cuda payload.' }
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
if (-not $SkipCompile) {
    & $Compiler /Q "/DPayloadDir=$Payload" "/DReleaseDir=$ReleaseDir" (Join-Path $PSScriptRoot 'packaging\installer-cuda.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Auto CUDA installer compilation failed.' }
}
Get-ChildItem -LiteralPath $ReleaseDir -File | Where-Object { $_.Extension -in '.exe', '.bin' } | ForEach-Object {
    $Hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    "$($Hash.Hash.ToLowerInvariant())  $($_.Name)" | Set-Content -LiteralPath ($_.FullName + '.sha256') -Encoding ascii
}
Write-Output "Installer files: $ReleaseDir"
