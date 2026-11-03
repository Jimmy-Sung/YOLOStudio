"""YOLO runs in a separate process so the application remains responsive."""
import json
import os
import sys
import traceback
from pathlib import Path

from core import AppError, Store, require
from runtime_paths import pretrained_path


def run(root, job_id):
    store = Store(root)
    job = store.get("jobs", job_id)
    cfg = job["config"]
    store.update_job(job_id, status="running", message="loading_engine")
    try:
        import torch
        from ultralytics import YOLO

        device_req = str(cfg.get("device", "auto")).lower()
        device = "cpu"
        if device_req in ("auto", "gpu") or device_req.isdigit():
            gpu_idx = int(device_req) if device_req.isdigit() else int(os.environ.get('YOLO_STUDIO_GPU_INDEX', '0'))
            if gpu_idx < 0:
                gpu_idx = 0
            if torch.cuda.is_available() and gpu_idx < torch.cuda.device_count():
                try:
                    torch.ones(1, device=f'cuda:{gpu_idx}').add_(1).cpu()
                    device = gpu_idx
                    gpu_name = torch.cuda.get_device_name(gpu_idx)
                    print(f"[Device] Using GPU {gpu_idx}: {gpu_name}")
                except Exception as exc:
                    print(f"[Device] GPU allocation failed ({exc}), automatically falling back to CPU")
                    device = "cpu"
                    store.update_job(job_id, message="gpu_fallback_cpu")
            else:
                print(f"[Device] GPU/CUDA not available, automatically falling back to CPU")
                device = "cpu"
                if device_req.isdigit():
                    store.update_job(job_id, message="gpu_fallback_cpu")
        else:
            device = "cpu"
        project = store.get("projects", job["project"])
        source = cfg["model"]
        if cfg.get("model_id"):
            source = str(store.path(store.get("models", cfg["model_id"])["path"]))
        else:
            source = str(pretrained_path(source,store.root))
        model = YOLO(source, task="detect")
        require(model.task == "detect", "detection_only")
        if job["kind"] == "autolabel":
            images = cfg["images"]
            names = model.names
            mapping = {i: project["classes"].index(n) for i, n in names.items() if n in project["classes"]}
            require(bool(mapping), "class_mismatch", ", ".join(names.values()))
            skipped = 0
            for i, item in enumerate(images):
                im = store.get("images", item["id"])
                result = model.predict(source=str(store.path(im["path"])), conf=cfg["confidence"], device=device, verbose=False)[0]
                boxes = []
                for coords, cls, confidence in zip(result.boxes.xyxyn.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
                    if int(cls) not in mapping:
                        continue
                    x1, y1, x2, y2 = [max(0., min(1., float(v))) for v in coords]
                    if x2 > x1 and y2 > y1:
                        boxes.append({"class_id": mapping[int(cls)], "x": x1, "y": y1, "w": x2-x1, "h": y2-y1, "confidence": confidence})
                with store.db() as db:
                    cur = db.execute("UPDATE images SET proposals=?,status='pending',revision=revision+1 WHERE id=? AND revision=? AND deleted=0 AND status IN ('unlabeled','draft','pending')", (json.dumps(boxes), im["id"], item["revision"]))
                    skipped += int(cur.rowcount == 0)
                store.update_job(job_id, progress=(i+1)/len(images), message=f"{i+1}/{len(images)}")
            store.update_job(job_id, status="completed", progress=1, result={"processed": len(images)-skipped, "skipped": skipped, "matched_classes": list(mapping.values())}, message="autolabel_done")
        else:
            job_dir = store.path(f"jobs/{job_id}")
            manifest = json.loads((job_dir / "dataset/manifest.json").read_text(encoding="utf-8"))

            def batch_end(trainer):
                try:
                    total_batches = len(trainer.train_loader) if getattr(trainer, 'train_loader', None) else 1
                    b_idx = getattr(trainer, 'batch_i', 0)
                    if (b_idx + 1) % 5 == 0 or b_idx == 0:
                        ep = getattr(trainer, 'epoch', 0)
                        prog = (ep + (b_idx + 1) / total_batches) / cfg['epochs'] * 0.9
                        store.update_job(
                            job_id,
                            status="running",
                            progress=min(0.9, max(0.01, prog)),
                            message=f"epoch {ep+1}/{cfg['epochs']} ({b_idx+1}/{total_batches})"
                        )
                except Exception:
                    pass

            def epoch_end(trainer):
                epoch = min(trainer.epoch+1, cfg['epochs'])
                store.update_job(job_id, status="running", progress=epoch/cfg["epochs"] * .9, message=f"epoch {epoch}/{cfg['epochs']}")

            model.add_callback("on_train_batch_end", batch_end)
            model.add_callback("on_fit_epoch_end", epoch_end)
            model.train(data=str(job_dir / "dataset/data.yaml"), epochs=cfg["epochs"], imgsz=cfg["imgsz"], batch=cfg["batch"], device=device, workers=0, project=str(job_dir), name="run", exist_ok=True, seed=42, deterministic=True, plots=True)
            best_path = job_dir / "run/weights/best.pt"
            require(best_path.is_file(), "model_missing")
            best = YOLO(str(best_path))
            store.update_job(job_id, message="evaluating", progress=.95)
            metrics = best.val(data=str(job_dir / "dataset/data.yaml"), split="test", device=device, workers=0, project=str(job_dir), name="test", plots=True)
            scores = {"precision": float(metrics.box.mp), "recall": float(metrics.box.mr), "map50": float(metrics.box.map50), "map50_95": float(metrics.box.map)}
            metadata = {"classes": manifest["project"]["classes"], "metrics": scores, "dataset_counts": manifest["counts"], "dataset_version": job_id, "config": cfg, "effective_device": str(device), "torch_version":torch.__version__, "cuda_runtime":torch.version.cuda, "gpu_name":torch.cuda.get_device_name(device) if device!='cpu' else None}
            registered = store.register_model(job["project"], cfg["name"], best_path, job_id, metadata)
            store.update_job(job_id, status="completed", progress=1, message="training_done", result={"model_id": registered["id"], **metadata})
    except Exception as exc:
        traceback.print_exc()
        store.update_job(job_id, status="failed", message=exc.code if isinstance(exc, AppError) else ("engine_missing" if isinstance(exc, ImportError) else "engine_error"), result={"detail": str(exc)})


if __name__ == "__main__":
    run(Path(sys.argv[1]), sys.argv[2])
