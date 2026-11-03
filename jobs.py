"""Background YOLO process manager for the native desktop application."""
import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path

from core import require, safe_name

BASE = Path(__file__).resolve().parent
PRETRAINED = {'yolo11n.pt', 'yolo11s.pt', 'yolov10n.pt'}


def get_worker_python():
    override = os.environ.get('YOLO_STUDIO_ENGINE_PYTHON') or os.environ.get('YOLO_STUDIO_PYTHON')
    if override and Path(override).is_file():
        return str(Path(override).resolve())
    for candidate in [
        BASE.parent / 'engines' / 'cu128' / 'python.exe',
        BASE.parent / 'engines' / 'cu126' / 'python.exe',
        BASE / 'engines' / 'cu128' / 'python.exe',
        BASE / 'engines' / 'cu126' / 'python.exe',
        Path(r'D:\YOLOStudio-CUDA-Build\payload\engines\cu128\python.exe'),
        Path(r'D:\YOLOStudio-CUDA-Build\payload\engines\cu126\python.exe'),
    ]:
        if candidate.is_file():
            return str(candidate.resolve())
    return sys.executable


class JobManager:
    @classmethod
    def terminate_lingering_workers(cls):
        """Ensure no leftover worker processes from previous runs linger in background."""
        if sys.platform == 'win32':
            try:
                import psutil
                my_pid = os.getpid()
                base_str = str(BASE).lower()
                for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if p.info['pid'] == my_pid:
                        continue
                    cmdline = p.info.get('cmdline') or []
                    cmd_str = ' '.join(str(c).lower() for c in cmdline)
                    if 'worker.py' in cmd_str and (base_str in cmd_str or 'yololabel' in cmd_str):
                        try:
                            p.kill()
                        except Exception:
                            pass
            except Exception:
                pass

    def __init__(self, store):
        self.store, self.processes, self.lock = store, {}, threading.Lock()
        with store.db() as db:
            active = db.execute("SELECT id FROM jobs WHERE status IN ('running','queued')").fetchall()
            import time
            now_ts = time.time()
            for row in active:
                jid = row[0]
                log_file = self.store.path(f"jobs/{jid}/worker.log")
                if log_file.exists() and (now_ts - log_file.stat().st_mtime < 60):
                    continue
                db.execute("UPDATE jobs SET status='interrupted',message='interrupted' WHERE id=?", (jid,))

    @staticmethod
    def engine_available():
        return importlib.util.find_spec('ultralytics') is not None

    def start(self, project, kind, config):
        with self.lock:
            require(self.engine_available(), 'engine_missing')
            require(kind in {'train','autolabel'}, 'invalid_request')
            config = dict(config)
            require(config.get('model') in PRETRAINED or config.get('model_id'), 'invalid_model')
            if config.get('model_id'):
                require(self.store.get('models',config['model_id'])['project'] == project, 'invalid_model')
            config['model'] = config.get('model','yolo11n.pt')
            device=config.get('device','auto')
            require(device in {'auto','cpu'} or (isinstance(device,str) and device.isdigit() and int(device)<64), 'invalid_parameters')
            if kind == 'train':
                for key, low, high in [('epochs',1,10000),('batch',1,128),('imgsz',64,2048)]:
                    require(type(config.get(key)) is int and low <= config[key] <= high, 'invalid_parameters')
                require(config['imgsz']%32 == 0, 'invalid_parameters')
                config['name'] = safe_name(config.get('name',''))
                reviewed = [im for im in self.store.list('images',project) if im['status'] in ('reviewed','empty')]
                require(len(reviewed)>=3, 'need_reviewed_images')
                require(any(im['boxes'] for im in reviewed), 'need_positive_labels')
            else:
                require(type(config.get('confidence')) in (int,float) and .01 <= config['confidence'] <= .99, 'invalid_parameters')
                config['images'] = [{'id':im['id'],'revision':im['revision']} for im in self.store.list('images',project) if im['status'] in ('unlabeled','draft','pending')]
                require(bool(config['images']), 'no_pending_images')
            job = self.store.create_job(project,kind,config)
            try:
                if kind == 'train':
                    self.store.snapshot(project,self.store.path(f"jobs/{job['id']}/dataset"))
                env = {**os.environ,'PYTHONIOENCODING':'utf-8','YOLO_CONFIG_DIR':str(self.store.path('runtime/yolo')),'MPLCONFIGDIR':str(self.store.path('runtime/matplotlib'))}
                with self.store.path(f"jobs/{job['id']}/worker.log").open('wb') as log:
                    worker_py = get_worker_python()
                    process = subprocess.Popen([worker_py,'-X','utf8','-B','-u',str(BASE/'worker.py'),str(self.store.root),job['id']],cwd=str(BASE),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.processes[job['id']] = process
                threading.Thread(target=self.watch,args=(job['id'],process),daemon=True).start()
            except Exception:
                self.store.update_job(job['id'],status='failed',message='launch_failed')
                raise
            return job

    def watch(self, identity, process):
        process.wait()
        with self.lock:
            if self.store.get('jobs',identity)['status'] in ('queued','running'):
                self.store.update_job(identity,status='failed',message='worker_stopped')
            self.processes.pop(identity,None)

    def cancel(self, identity):
        with self.lock:
            process = self.processes.get(identity)
            require(process is not None and process.poll() is None,'job_finished')
            process.terminate()
            process.wait(timeout=15)
            if self.store.get('jobs',identity)['status'] in ('queued','running'):
                self.store.update_job(identity,status='cancelled',message='cancelled')

    def close(self):
        for identity in list(self.processes):
            try:
                self.cancel(identity)
            except Exception:
                pass

    def log(self,identity):
        self.store.get('jobs',identity)
        path = self.store.path(f'jobs/{identity}/worker.log')
        if not path.exists():
            return ''
        with path.open('rb') as f:
            f.seek(max(0,path.stat().st_size-24000))
            return f.read().decode('utf-8',errors='replace')
