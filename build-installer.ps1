param(
    [switch]$SkipPayloadBuild,
    [string]$Compiler = '',
    [string]$Payload = '',
    [string]$ReleaseDir = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Payload) { $Payload = Join-Path $PSScriptRoot 'dist\YOLO Studio' }
if (-not $ReleaseDir) { $ReleaseDir = Join-Path $PSScriptRoot 'output\installers' }
if (-not $Compiler) {
    $compilerCandidates = @(
        (Join-Path $PSScriptRoot 'tmp\installer-tools\Inno Setup\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 7\ISCC.exe'
    )
    $Compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler) { throw 'Install Inno Setup or pass -Compiler with the full path to ISCC.exe.' }
if (-not $SkipPayloadBuild) {
    & (Join-Path $PSScriptRoot 'build-launcher.ps1')
    & (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'tools\build_distribution.py') --profile cpu --output $Payload --clean
    if ($LASTEXITCODE -ne 0) { throw 'Standalone runtime build failed.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $Payload 'distribution.json'))) { throw 'Standalone payload is missing distribution.json.' }
$payloadInfo = Get-Content -LiteralPath (Join-Path $Payload 'distribution.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($payloadInfo.profile -ne 'cpu') { throw 'This installer definition is for CPU builds; do not label a CUDA payload as CPU.' }
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
& $Compiler /Q "/DPayloadDir=$Payload" "/DReleaseDir=$ReleaseDir" (Join-Path $PSScriptRoot 'packaging\installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
Get-ChildItem -LiteralPath $ReleaseDir -Filter '*Setup.exe' | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    "$($hash.Hash.ToLowerInvariant())  $($_.Name)" | Set-Content -LiteralPath ($_.FullName + '.sha256') -Encoding ascii
}
