param([int]$RepairProcessId)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
Start-Transcript -Path 'D:\YOLOStudio-CUDA-Build\download-recovery.log' -Append | Out-Null
try {
    if ($RepairProcessId) { Wait-Process -Id $RepairProcessId -ErrorAction SilentlyContinue }
    for ($Attempt = 1; $Attempt -le 6; $Attempt++) {
        & (Join-Path $ProjectRoot '.venv\Scripts\python.exe') (Join-Path $PSScriptRoot 'fetch_cuda_wheels.py')
        if ($LASTEXITCODE -eq 0) { exit 0 }
        Write-Output "Download verification attempt $Attempt failed; retaining partial downloads."
        Start-Sleep -Seconds 10
    }
    throw 'CUDA download recovery failed; see download-recovery.log.'
} finally { Stop-Transcript | Out-Null }
