$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
& $compiler /nologo /target:winexe /platform:x64 /main:Launcher '/out:YOLO Studio.exe' '/win32icon:assets\app-icon.ico' /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll launcher.cs gpu_selector.cs
if ($LASTEXITCODE -ne 0) { throw 'Could not build the YOLO Studio launcher.' }
Write-Host 'Built YOLO Studio.exe with the application icon.'
& $compiler /nologo /target:exe /platform:x64 /main:GpuDetect /out:GpuDetect.exe /reference:System.Web.Extensions.dll gpu_selector.cs
if ($LASTEXITCODE -ne 0) { throw 'Could not build the GPU selector.' }
