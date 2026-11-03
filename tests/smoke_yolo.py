"""Opt-in real CPU smoke test. Uses synthetic data and random initial weights.

Run: .venv/Scripts/python.exe tests/smoke_yolo.py
This verifies execution, never production model quality.
"""
import io
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from PIL import Image,ImageDraw
from core import Store
from jobs import JobManager


def wait(store,manager,identity,timeout=180):
    deadline=time.monotonic()+timeout
    previous=''
    while time.monotonic()<deadline:
        job=store.get('jobs',identity)
        assert 0 <= job['progress'] <= 1, job
        message=f"{job['status']} {job['progress']:.0%} {job['message']}"
        if message!=previous:print(message,flush=True);previous=message
        if job['status'] not in ('queued','running'):
            if job['status']!='completed':
                print(manager.log(identity),flush=True)
                raise AssertionError(job)
            # Watcher removes the process after the final DB write.
            for _ in range(50):
                if identity not in manager.processes:break
                time.sleep(.1)
            return job
        time.sleep(.5)
    manager.cancel(identity)
    raise AssertionError('Timed out waiting for YOLO')


def main():
    (BASE/'tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='yolo-smoke-',dir=BASE/'tmp') as root:
        os.environ['YOLO_CONFIG_DIR']=str(Path(root)/'runtime/yolo')
        os.environ['MPLCONFIGDIR']=str(Path(root)/'runtime/matplotlib')
        from ultralytics import YOLO
        store=Store(Path(root)/'data');manager=JobManager(store)
        project=store.create_project('流程驗證_非正式模型','TEST',['screw'])
        images=[]
        for i in range(6):
            image=Image.new('RGB',(128,128),(20+i*3,60,45));draw=ImageDraw.Draw(image);draw.rectangle((32,32,96,96),fill=(220,220,210));content=io.BytesIO();image.save(content,format='PNG')
            im=store.import_image(project['id'],f'sample-{i}.png',content.getvalue());images.append(im)
            if i<5:store.save_image(im['id'],[{'class_id':0,'x':.25,'y':.25,'w':.5,'h':.5}],0,reviewed=True)
        seed=store.path('models/seed.pt');seed.parent.mkdir(parents=True);YOLO('yolo11n.yaml').save(seed)
        source=store.register_model(project['id'],'random-seed-test-only',seed)
        try:
            training=manager.start(project['id'],'train',{'model_id':source['id'],'name':'smoke_v001','epochs':1,'batch':2,'imgsz':128,'device':'cpu'})
            result=wait(store,manager,training['id'])
            assert result['result']['dataset_counts']=={'train':3,'val':1,'test':1},result
            model_id=result['result']['model_id']
            archive=store.model_package(model_id,'流程測試_v001')
            with zipfile.ZipFile(archive) as z:
                assert '流程測試_v001.pt' in z.namelist()
                assert 'dataset/manifest.json' in z.namelist()
                assert 'classes.json' in z.namelist()
                assert 'run/results.csv' in z.namelist()
            automatic=manager.start(project['id'],'autolabel',{'model_id':model_id,'confidence':.01,'device':'cpu'})
            wait(store,manager,automatic['id'])
            im=store.get('images',images[-1]['id'])
            assert im['status']=='pending',im
            assert sum(i['status']=='reviewed' for i in store.list('images',project['id']))==5
            stopping=manager.start(project['id'],'train',{'model_id':model_id,'name':'cancel_test','epochs':10,'batch':2,'imgsz':128,'device':'cpu'})
            manager.cancel(stopping['id'])
            assert store.get('jobs',stopping['id'])['status']=='cancelled'
            assert len(store.list('models',project['id']))==2
            print('PASS: actual CPU training, held-out evaluation, auto-label review gate, cancellation and named model ZIP.',flush=True)
        finally:manager.close()


if __name__=='__main__':main()
