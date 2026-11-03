"""Assemble CPU plus two private CUDA runtimes without changing development Python."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from datetime import datetime,timezone

BASE=Path(__file__).resolve().parents[1]
BUILD=Path('D:/YOLOStudio-CUDA-Build')
MODULES=('app.py','app_icon.py','canvas.py','core.py','dataset.py','desktop.py','jobs.py','worker.py','runtime_paths.py','installer_check.py','translations.json')


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    global BUILD
    parser=argparse.ArgumentParser();parser.add_argument('--build-root',type=Path,default=BUILD);parser.add_argument('--output',type=Path);parser.add_argument('--clean',action='store_true');args=parser.parse_args();BUILD=args.build_root.resolve();output=(args.output or BUILD/'payload').resolve()
    if output.exists():
        if not args.clean:
            raise RuntimeError('Refusing to overwrite '+str(output))
        print('Updating payload files in place (preserving active engines)...',flush=True)
        shutil.copytree(BASE/'dist/YOLO Studio',output,dirs_exist_ok=True,ignore=shutil.ignore_patterns('engines'))
    else:
        print('Copying verified CPU baseline...',flush=True)
        shutil.copytree(BASE/'dist/YOLO Studio',output)
    plan=json.loads((BUILD/'download-plan.json').read_text())
    for item in plan:
        wheel=BUILD/'wheels'/item['filename']
        if not wheel.is_file() or digest(wheel)!=item['sha256']:raise RuntimeError('Wheel missing or hash mismatch: '+str(wheel))
    for name in MODULES:shutil.copy2(BASE/name,output/'app'/name)
    for name in ('YOLO Studio.exe','GpuDetect.exe'):shutil.copy2(BASE/name,output/name)
    # Ultralytics uses a separate tiny model for its GPU AMP consistency check.
    # Bundle it too so that first GPU training does not fetch additional weights.
    amp=BASE/'tmp/package-weights/yolo26n.pt'
    if not amp.is_file():raise RuntimeError('Missing AMP check weight: '+str(amp))
    (output/'app/weights').mkdir(exist_ok=True)
    shutil.copy2(amp,output/'app/weights/yolo26n.pt')
    profiles=[]
    for profile in ('cu126','cu128'):
        engine=output/'engines'/profile;site=engine/'Lib/site-packages';site.mkdir(parents=True,exist_ok=True)
        engine_ready=False
        if (engine/'python.exe').is_file():
            try:
                env={**os.environ,'YOLO_CONFIG_DIR':str(BUILD/'checks/build-config'),'PYTHONIOENCODING':'utf-8'}
                probe=subprocess.run([str(engine/'python.exe'),'-X','utf8','-B','-c',"import torch,json; print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'archs':torch.cuda.get_arch_list(),'available':torch.cuda.is_available()}))"],cwd=BUILD,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
                info=json.loads(probe.stdout.decode('utf-8').strip().splitlines()[-1])
                engine_ready=True
                print(f'{profile} verified in place:',info,flush=True)
            except Exception:
                engine_ready=False
        if not engine_ready:
            for source in (output/'runtime').iterdir():
                if source.suffix.lower() in ('.exe','.dll'):shutil.copy2(source,engine/source.name)
            (engine/'python312._pth').write_text('../../runtime/Lib\n../../runtime/DLLs\nLib/site-packages\n../../runtime/Lib/site-packages\n../../app\nimport site\n',encoding='utf-8')
            for item in plan:
                if item['profile']!=profile:continue
                print('Extracting '+item['filename'],flush=True)
                with zipfile.ZipFile(BUILD/'wheels'/item['filename']) as wheel:
                    for member in wheel.infolist():
                        target=(site/member.filename).resolve()
                        if not target.is_relative_to(site.resolve()):raise RuntimeError('Invalid wheel path')
                        wheel.extract(member,site)
            env={**os.environ,'YOLO_CONFIG_DIR':str(BUILD/'checks/build-config'),'PYTHONIOENCODING':'utf-8'}
            probe=subprocess.run([str(engine/'python.exe'),'-X','utf8','-B','-c',"import torch,json; print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'archs':torch.cuda.get_arch_list(),'available':torch.cuda.is_available()}))"],cwd=BUILD,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            info=json.loads(probe.stdout.decode('utf-8').strip().splitlines()[-1]);print(profile,info,flush=True)
        arches=[int(re.match(r'sm_(\d+)',a).group(1)) for a in info['archs'] if re.match(r'sm_(\d+)',a)]
        assert info['cuda']==('12.6' if profile=='cu126' else '12.8') and arches
        profiles.append({'id':profile,'label':'CUDA '+info['cuda'],'python':f'engines/{profile}/pythonw.exe','min_driver_api':12060 if profile=='cu126' else 12080,'priority':126 if profile=='cu126' else 128,'archs':arches,'torch':info['torch'],'cuda_runtime':info['cuda'],'wheel_sha256':{x['filename']:x['sha256'] for x in plan if x['profile']==profile}})
    catalog={'profiles':profiles};(output/'engine-catalog.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    marker=json.loads((output/'distribution.json').read_text(encoding='utf-8'));marker.update({'version':'0.3.1','profile':'auto-cuda','engines':profiles,'amp_check_weight':{'path':'app/weights/yolo26n.pt','sha256':digest(amp)},'created':datetime.now(timezone.utc).isoformat(),'selection':'NVIDIA Driver API + compute capability; compatible CUDA 12.8 / CUDA 12.6 / CPU'})
    (output/'distribution.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ('README.md','INSTALLATION.md'):shutil.copy2(BASE/'packaging/INSTALLATION-CUDA.md',output/name)
    (output/'app/source-checksums.json').write_text(json.dumps({name:digest(output/'app'/name) for name in MODULES},indent=2))
    print('Built auto-CUDA payload: '+str(output),flush=True)


if __name__=='__main__':main()
