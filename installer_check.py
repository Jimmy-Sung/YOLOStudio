"""Validate a relocated installation using only its bundled runtime."""
import argparse
import io
import json
import os
import sys
import tempfile
import time
import traceback
import zipfile
from datetime import datetime,timezone
from pathlib import Path

from runtime_paths import APP_ROOT,default_data_dir,distribution_info,pretrained_path


def wait_job(store,manager,identity,timeout=240):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=store.get('jobs',identity)
        if job['status'] not in ('queued','running'):
            if job['status']!='completed':raise RuntimeError(json.dumps(job,ensure_ascii=False)+'\n'+manager.log(identity))
            for _ in range(100):
                if identity not in manager.processes:break
                time.sleep(.1)
            return job
        time.sleep(.3)
    manager.cancel(identity);raise TimeoutError('Training worker did not finish')


def check(train=False,device='cpu',require_cuda=False):
    import importlib.metadata as metadata
    from PIL import Image,ImageDraw
    import torch,torchvision,ultralytics
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from core import Store
    from desktop import MainWindow
    from jobs import JobManager
    from ultralytics import YOLO

    report={'checked':datetime.now(timezone.utc).isoformat(),'python':sys.version,'executable':sys.executable,'isolated':bool(sys.flags.isolated),'sys_path':sys.path,'torch':torch.__version__,'cuda_runtime':torch.version.cuda,'cuda_available':torch.cuda.is_available(),'torchvision':torchvision.__version__,'ultralytics':ultralytics.__version__,'distribution':distribution_info(),'default_data_directory':str(default_data_dir()),'checks':[]}
    if distribution_info():
        root=APP_ROOT.parent.resolve()
        assert Path(sys.executable).resolve().is_relative_to(root)
        assert Path(torch.__file__).resolve().is_relative_to(root)
        assert sys.flags.isolated
    assert torch.isfinite(torch.ones((4,4)).matmul(torch.ones((4,4)))).all()
    # Exercise torchvision's compiled CPU operator rather than just importing it.
    keep=torchvision.ops.nms(torch.tensor([[0.,0.,10.,10.],[1.,1.,9.,9.]]),torch.tensor([.9,.8]),.5)
    assert keep.tolist()==[0]
    report['checks'].append('torch tensor and torchvision native NMS')
    if require_cuda:
        assert torch.cuda.is_available(),'CUDA is not available'
        index=int(device) if device.isdigit() else 0
        a=torch.ones((8,8),device=f'cuda:{index}');assert torch.isfinite(a@a).all().item()
        keep=torchvision.ops.nms(torch.tensor([[0.,0.,10.,10.],[1.,1.,9.,9.]],device=f'cuda:{index}'),torch.tensor([.9,.8],device=f'cuda:{index}'),.5)
        assert keep.cpu().tolist()==[0];torch.cuda.synchronize(index)
        report['gpu_name']=torch.cuda.get_device_name(index);report['gpu_capability']=list(torch.cuda.get_device_capability(index));report['compiled_architectures']=torch.cuda.get_arch_list();report['checks'].append('actual CUDA tensor kernels and torchvision CUDA NMS')
    app=QApplication.instance() or QApplication([])
    parent=Path(os.environ['YOLO_CONFIG_DIR']).parent/'checks';parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='isolated-',dir=parent) as directory:
        store=Store(Path(directory)/'工作資料');project=store.create_project('安裝包流程驗證','ST01',['screw'])
        manager=JobManager(store);window=MainWindow(store,manager);window.timer.stop();errors=[];window.error=errors.append
        try:
            window.show();app.processEvents()
            for index in range(3):window.language.setCurrentIndex(index);app.processEvents()
            assert not window.windowIcon().pixmap(32,32).isNull()
            window.close();assert not errors,errors
            report['checks'].append('native Qt window, icon and three languages')
            for name in ('yolo11n.pt','yolo11s.pt','yolov10n.pt'):
                path=pretrained_path(name,store.root)
                assert path.is_file(),str(path)
                assert YOLO(str(path)).task=='detect'
            report['checks'].append('all three bundled pretrained detection models')
            if train:
                for i in range(6):
                    image=Image.new('RGB',(128,128),(20+i*3,60,45));draw=ImageDraw.Draw(image);draw.rectangle((32,32,96,96),fill=(220,220,210));content=io.BytesIO();image.save(content,format='PNG')
                    im=store.import_image(project['id'],f'sample-{i}.png',content.getvalue())
                    if i<5:store.save_image(im['id'],[{'class_id':0,'x':.25,'y':.25,'w':.5,'h':.5}],0,reviewed=True)
                job=manager.start(project['id'],'train',{'model':'yolo11n.pt','name':'installer_validation','epochs':1,'batch':2,'imgsz':128,'device':device})
                result=wait_job(store,manager,job['id']);model_id=result['result']['model_id']
                archive=store.model_package(model_id,'安裝包測試模型')
                with zipfile.ZipFile(archive) as z:assert '安裝包測試模型.pt' in z.namelist() and 'dataset/manifest.json' in z.namelist()
                automatic=manager.start(project['id'],'autolabel',{'model_id':model_id,'confidence':.01,'device':device});wait_job(store,manager,automatic['id'])
                assert sum(im['status']=='pending' for im in store.list('images',project['id']))==1
                stopping=manager.start(project['id'],'train',{'model_id':model_id,'name':'cancel_check','epochs':10,'batch':2,'imgsz':128,'device':'cpu'});manager.cancel(stopping['id']);assert store.get('jobs',stopping['id'])['status']=='cancelled'
                report['checks'].append('background '+('CUDA' if require_cuda else 'CPU')+' training, held-out evaluation, auto-labeling, named export and cancellation')
                report['training_metrics']=result['result']['metrics']
                report['training_device']=result['result']['effective_device']
                if require_cuda:assert report['training_device']!='cpu'
        finally:manager.close();window.close();app.processEvents()
    report['ok']=True
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,default=default_data_dir().parent/'environment-report.json');parser.add_argument('--train',action='store_true');parser.add_argument('--work',type=Path);parser.add_argument('--device',default='cpu');parser.add_argument('--require-cuda',action='store_true');args=parser.parse_args()
    work=args.work or default_data_dir()/'runtime'/'diagnostics';work.mkdir(parents=True,exist_ok=True)
    os.environ['YOLO_CONFIG_DIR']=str(work/'yolo');os.environ['MPLCONFIGDIR']=str(work/'matplotlib');os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['YOLO_OFFLINE']='true';os.environ['YOLO_AUTOINSTALL']='false';os.environ['PYTHONIOENCODING']='utf-8'
    args.report.parent.mkdir(parents=True,exist_ok=True)
    try:report=check(args.train,args.device,args.require_cuda)
    except Exception:
        report={'ok':False,'error':traceback.format_exc(),'executable':sys.executable};print(report['error'],flush=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(('PASS' if report['ok'] else 'FAIL')+' '+str(args.report),flush=True)
    return 0 if report['ok'] else 1


if __name__=='__main__':sys.exit(main())
