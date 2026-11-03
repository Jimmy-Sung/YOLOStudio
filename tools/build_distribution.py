"""Build an isolated Windows runtime from the tested environment, not a copied venv.

Run with the environment to package. Both CPU and CUDA profiles are supported;
the profile must match torch.version.cuda in that environment.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BASE=Path(__file__).resolve().parents[1]
VERSION='0.3.1'
ROOTS=('ultralytics','torchvision','PySide6-Essentials','Pillow')
MODULES=('app.py','app_icon.py','canvas.py','core.py','dataset.py','desktop.py','jobs.py','worker.py','runtime_paths.py','installer_check.py','translations.json')
WEIGHT_VERSION='v8.3.0'
WEIGHTS=('yolo11n.pt','yolo11s.pt','yolov10n.pt')


def dependency_closure():
    result={};queue=list(ROOTS)
    while queue:
        name=queue.pop();key=canonicalize_name(name)
        if key in result:continue
        dist=metadata.distribution(name);result[key]=dist
        for raw in dist.requires or []:
            requirement=Requirement(raw)
            if requirement.marker and not requirement.marker.evaluate({'extra':''}):continue
            dependency=metadata.distribution(requirement.name)
            if requirement.specifier and not requirement.specifier.contains(dependency.version,prereleases=True):
                raise RuntimeError(f'Incompatible dependency: {raw}; installed {dependency.version}')
            queue.append(requirement.name)
    return result


def copy_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)


def hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['cpu','cuda'],default='cpu');parser.add_argument('--output',type=Path,default=BASE/'dist'/'YOLO Studio');parser.add_argument('--without-weights',action='store_true');parser.add_argument('--clean',action='store_true');args=parser.parse_args()
    if sys.platform!='win32' or platform.architecture()[0]!='64bit':raise RuntimeError('Build on Windows x64')
    import torch
    if (torch.version.cuda is not None)!=(args.profile=='cuda'):raise RuntimeError(f'Profile {args.profile} does not match installed torch {torch.__version__}, CUDA {torch.version.cuda}')
    output=args.output.resolve()
    if output.exists():
        if args.clean:
            print(f'Removing existing distribution: {output}',flush=True)
            shutil.rmtree(output)
        else:
            raise RuntimeError(f'Refusing to overwrite an existing distribution: {output}')
    print('Resolving tested dependency closure...',flush=True);dependencies=dependency_closure()
    runtime=output/'runtime';site=runtime/'Lib/site-packages';application=output/'app';runtime.mkdir(parents=True);application.mkdir()
    base=Path(sys.base_prefix)
    for name in ('python.exe','pythonw.exe','python3.dll','python312.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
        source=base/name
        if not source.is_file():raise RuntimeError(f'Missing runtime binary {source}')
        copy_file(source,runtime/name)
    print('Copying Python standard library...',flush=True)
    shutil.copytree(base/'DLLs',runtime/'DLLs',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(base/'Lib',runtime/'Lib',dirs_exist_ok=True,ignore=shutil.ignore_patterns('site-packages','__pycache__','*.pyc','test','tests','idlelib','tkinter','turtledemo'))
    site.mkdir(parents=True,exist_ok=True)
    records=[]
    for key,dist in sorted(dependencies.items()):
        print(f'Bundling {dist.metadata["Name"]} {dist.version}',flush=True)
        origin=Path(dist.locate_file('')).resolve()
        for entry in dist.files or []:
            if '..' in entry.parts or '__pycache__' in entry.parts or entry.suffix=='.pyc':continue
            source=Path(dist.locate_file(entry)).resolve()
            if source.is_file() and source.is_relative_to(origin):copy_file(source,site/Path(entry))
        records.append({'name':dist.metadata['Name'],'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License','See bundled package metadata')})
    # Place the dependency's redistributable CRT DLLs alongside the interpreter;
    # workers can import torch before importing Qt on a clean machine.
    for dll in (site/'PySide6').glob('*.dll'):
        if dll.name.lower().startswith(('msvcp','vcruntime','concrt','vcomp')):copy_file(dll,runtime/dll.name)
    (runtime/'python312._pth').write_text('Lib\nDLLs\nLib/site-packages\n../app\nimport site\n',encoding='utf-8')
    for name in MODULES:copy_file(BASE/name,application/name)
    shutil.copytree(BASE/'assets',application/'assets')
    copy_file(BASE/'README.md',output/'SOURCE-README.md')
    copy_file(BASE/'packaging/INSTALLATION.md',output/'README.md')
    copy_file(BASE/'packaging/INSTALLATION.md',output/'INSTALLATION.md')
    copy_file(BASE/'YOLO Studio.exe',output/'YOLO Studio.exe')
    # Preserve Python and all distribution-supplied license files and metadata.
    licenses=output/'licenses';licenses.mkdir();copy_file(base/'LICENSE.txt',licenses/'PYTHON-LICENSE.txt')
    (licenses/'THIRD_PARTY_NOTICES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    weights=[]
    if not args.without_weights:
        cache=BASE/'tmp/package-weights';cache.mkdir(parents=True,exist_ok=True)
        for name in WEIGHTS:
            cached=cache/name
            if not cached.exists():
                print('Downloading official pretrained weights: '+name,flush=True)
                urllib.request.urlretrieve(f'https://github.com/ultralytics/assets/releases/download/{WEIGHT_VERSION}/{name}',cached)
            from ultralytics import YOLO
            model=YOLO(str(cached));assert model.task=='detect'
            copy_file(cached,application/'models'/name);weights.append({'name':name,'sha256':hash_file(cached),'source':f'https://github.com/ultralytics/assets/releases/download/{WEIGHT_VERSION}/{name}'})
    info={'name':'YOLO Studio','version':VERSION,'profile':args.profile,'python':platform.python_version(),'torch':torch.__version__,'cuda_runtime':torch.version.cuda,'architecture':'Windows x64','minimum_windows':'Windows 10 22H2 / Windows 11','created':datetime.now(timezone.utc).isoformat(),'dependencies':[{'name':r['name'],'version':r['version']} for r in records],'pretrained_weights':weights,'data_directory':'%LOCALAPPDATA%/YOLOStudio/data','source_data_included':False}
    (output/'distribution.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'Check environment.cmd').write_text('@echo off\r\n"%~dp0runtime\\python.exe" -X utf8 -B "%~dp0app\\installer_check.py" --report "%LOCALAPPDATA%\\YOLOStudio\\environment-report.json"\r\npause\r\n',encoding='ascii')
    (output/'packages.lock.txt').write_text('\n'.join(f'{r["name"]}=={r["version"]}' for r in records)+'\n',encoding='utf-8')
    (application/'source-checksums.json').write_text(json.dumps({name:hash_file(application/name) for name in MODULES},indent=2),encoding='utf-8')
    total=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    print(f'Built {output}\nPayload size: {total/1024**2:.1f} MiB; {len(records)} pinned distributions',flush=True)


if __name__=='__main__':main()
