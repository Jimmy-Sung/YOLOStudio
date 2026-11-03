"""Run the installed executable in an intentionally unrelated Python environment."""
import argparse
import json
import os
import subprocess
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('payload',type=Path);parser.add_argument('--train',action='store_true');parser.add_argument('--name',default='standalone');parser.add_argument('--engine',default='cpu');parser.add_argument('--device',default='cpu');parser.add_argument('--require-cuda',action='store_true');args=parser.parse_args()
    payload=args.payload.resolve();work=BASE/'output/package-tests'/args.name;work.mkdir(parents=True,exist_ok=True)
    environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','COMSPEC','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}}
    environment.update({'PATH':str(Path(environment.get('SYSTEMROOT','C:/Windows'))/'System32'),'PYTHONHOME':'Z:/not-installed-python','PYTHONPATH':'Z:/not-installed-site-packages','VIRTUAL_ENV':'Z:/no-venv','YOLO_STUDIO_DATA':str(work/'private-data'),'YOLO_OFFLINE':'true','YOLO_AUTOINSTALL':'false'})
    # Refuse HTTP downloads within this diagnostic process and its workers.
    # This does not alter the computer's proxy settings.
    environment.update({'HTTP_PROXY':'http://127.0.0.1:9','HTTPS_PROXY':'http://127.0.0.1:9','ALL_PROXY':'http://127.0.0.1:9','NO_PROXY':''})
    python=payload/'runtime/python.exe' if args.engine=='cpu' else payload/'engines'/args.engine/'python.exe'
    command=[str(python),'-X','utf8','-B',str(payload/'app/installer_check.py'),'--report',str(work/'report.json'),'--work',str(work/'runtime'),'--device',args.device]
    if args.train:command.append('--train')
    if args.require_cuda:command.append('--require-cuda')
    print('Checking isolated runtime in '+str(payload),flush=True)
    result=subprocess.run(command,cwd=work,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=420)
    output=result.stdout.decode('utf-8',errors='replace');print(output,flush=True);(work/'console.log').write_text(output,encoding='utf-8')
    if result.returncode:raise SystemExit(result.returncode)
    report=json.loads((work/'report.json').read_text(encoding='utf-8'));assert report['ok'];assert report['isolated'];print('Verified checks: '+', '.join(report['checks']),flush=True)


if __name__=='__main__':main()
