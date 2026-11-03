"""Finish the local AutoCUDA release after verified wheel downloads complete.

Progress and failures are written to BUILD/release-status.json and release.log.
Never marks a release ready until real CUDA training and installation pass.
"""
import hashlib
import json
import subprocess
import sys
import time
import traceback
import winreg
import zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
BUILD=Path('D:/YOLOStudio-CUDA-Build')
PYTHON=BASE/'.venv/Scripts/python.exe'
STATUS=BUILD/'release-status.json'


def status(stage,**values):
    data={'stage':stage,'updated':time.strftime('%Y-%m-%d %H:%M:%S'),**values}
    STATUS.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False),flush=True)


def run(command,timeout=1800):
    print('Running: '+str(command),flush=True)
    subprocess.run([str(x) for x in command],cwd=BASE,check=True,timeout=timeout,stdout=sys.stdout,stderr=sys.stderr)


def main():
    status('waiting_for_wheels')
    plan=json.loads((BUILD/'download-plan.json').read_text())
    deadline=time.monotonic()+6*3600
    while not all((BUILD/'wheels'/x['filename']).is_file() for x in plan):
        if time.monotonic()>deadline:raise TimeoutError('CUDA wheel download did not finish within six hours.')
        time.sleep(10)
    status('building_payload')
    payload=BUILD/'payload'
    run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',BASE/'build-launcher.ps1'])
    run([PYTHON,BASE/'tools/build_auto_cuda.py','--output',payload])
    for engine in ('cu126','cu128'):
        status('validating_gpu',engine=engine)
        run([PYTHON,BASE/'tools/verify_distribution.py',payload,'--engine',engine,'--device','0','--require-cuda','--train','--name',engine+'-release'])
    status('validating_cpu_fallback')
    run([PYTHON,BASE/'tools/verify_distribution.py',payload,'--train','--name','autocuda-cpu-release'])
    selected=json.loads(subprocess.check_output([str(payload/'GpuDetect.exe'),'--root',str(payload)],cwd=BASE).decode('utf-8-sig'))
    if selected['id']!='cu128':raise RuntimeError('Build GPU was expected to select cu128: '+str(selected))
    status('compiling_installer',selected=selected)
    run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',BASE/'build-cuda-installer.ps1','-SkipPayloadBuild'],timeout=3600)
    # Avoid replacing the registration of an installation the user already owns.
    uninstall_key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{7E80C571-55E0-4F1F-A75C-B3C63A8C3C35}_is1'
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive,uninstall_key):raise RuntimeError('An existing YOLO Studio installation prevents isolated installer testing.')
        except FileNotFoundError:pass
    target=(BUILD/'Installed 中文 路徑/YOLO Studio').resolve()
    if not target.is_relative_to(BUILD.resolve()) or target.exists():raise RuntimeError('Installer test requires a fresh path inside the build directory.')
    release=BUILD/'installer'
    setup=release/'YOLO-Studio-0.3.0-Windows-x64-AutoCUDA-Setup.exe'
    status('testing_installer')
    run([setup,'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/TASKS=','/DIR='+str(target),'/LOG='+str(BUILD/'install.log')])
    finish(target,release,selected)


def finish(target,release,selected):
    if not target.resolve().is_relative_to(BUILD.resolve()):raise RuntimeError('Test installation must stay inside the build directory.')
    info=json.loads((target/'distribution.json').read_text(encoding='utf-8'))
    if info.get('profile')!='auto-cuda' or info.get('version')!='0.3.0':raise RuntimeError('Unexpected installed distribution.')
    if not (target/'engines/cu128/python.exe').is_file() or (target/'engines/cu126/python.exe').exists():raise RuntimeError('Installer did not install only the selected CUDA engine.')
    status('validating_installed_gpu')
    run([PYTHON,BASE/'tools/verify_distribution.py',target,'--engine','cu128','--device','0','--require-cuda','--train','--name','autocuda-installed'])
    run([PYTHON,BASE/'tools/verify_distribution.py',target,'--name','autocuda-installed-cpu'])
    run([target/'unins000.exe','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/LOG='+str(BUILD/'uninstall.log')])
    status('packaging_release')
    reports={}
    for name in ('cu126-release','cu128-release','autocuda-cpu-release','autocuda-installed','autocuda-installed-cpu'):
        reports[name]=json.loads((BASE/'output/package-tests'/name/'report.json').read_text(encoding='utf-8'))
    verification={'ok':True,'selected':selected,'reports':reports,'tested_hardware':'NVIDIA RTX 3070 Laptop GPU; other hardware selection paths tested with fixtures'}
    (release/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    (release/'安裝說明.md').write_text((BASE/'packaging/INSTALLATION-CUDA.md').read_text(encoding='utf-8'),encoding='utf-8')
    output=BASE/'output/installers/cuda';output.mkdir(parents=True,exist_ok=True)
    archive=output/'YOLO-Studio-0.3.0-Windows-x64-AutoCUDA.zip'
    if archive.exists():raise RuntimeError('Refusing to overwrite an existing release archive.')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as bundle:
        for path in sorted(release.iterdir()):
            if path.is_file():bundle.write(path,path.name)
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    status('ready',archive=str(archive),bytes=archive.stat().st_size,sha256=digest,selected=selected)


if __name__=='__main__':
    BUILD.mkdir(parents=True,exist_ok=True)
    with (BUILD/'release.log').open('a',encoding='utf-8',buffering=1) as log:
        sys.stdout=log;sys.stderr=log
        try:
            if '--finish-installed' in sys.argv:
                target=BUILD/'Installed 中文 路徑/YOLO Studio'
                selected=json.loads(subprocess.check_output([str(target/'GpuDetect.exe'),'--root',str(target)],cwd=BASE).decode('utf-8-sig'))
                finish(target,BUILD/'installer',selected)
            else:main()
        except Exception as error:
            status('failed',error=str(error));traceback.print_exc();raise
