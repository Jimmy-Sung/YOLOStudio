param([switch]$WithYolo)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') {
        $bootstrapPython = $pythonCommand.Source
    } elseif (Test-Path -LiteralPath $bundledPython) {
        $bootstrapPython = $bundledPython
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.10+ from python.org, then run setup.ps1 again.' }
    } else { throw 'Install Python 3.10+ from python.org, then run setup.ps1 again.' }
    if ($bootstrapPython) {
        & $bootstrapPython -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
    }
}
$requirements = if ($WithYolo) { 'requirements-yolo.txt' } else { 'requirements.txt' }
& $venvPython -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and the pip output above.' }
Write-Host 'Setup complete. Run .\start.ps1 to launch YOLO Studio.'
