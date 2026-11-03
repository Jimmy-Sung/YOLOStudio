"""Persistent projects, annotations, reproducible datasets and model packages."""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import shutil
import sqlite3
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, ImageEnhance


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid():
    return uuid.uuid4().hex


class AppError(Exception):
    def __init__(self, code, detail="", status=400):
        self.code, self.detail, self.status = code, detail, status
        super().__init__(f"{code}: {detail}")


def require(condition, code, detail="", status=400):
    if not condition:
        raise AppError(code, detail, status)


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip(" .")[:100]
    require(bool(value), "invalid_name")
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}:
        value = "_" + value
    return value


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS projects(
              id TEXT PRIMARY KEY, name TEXT NOT NULL, station TEXT NOT NULL,
              classes TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS images(
              id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id),
              name TEXT NOT NULL, path TEXT NOT NULL, width INTEGER NOT NULL,
              height INTEGER NOT NULL, digest TEXT NOT NULL,
              boxes TEXT NOT NULL DEFAULT '[]', proposals TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'unlabeled', revision INTEGER NOT NULL DEFAULT 0,
              UNIQUE(project,digest));
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id),
              kind TEXT NOT NULL, status TEXT NOT NULL, config TEXT NOT NULL,
              progress REAL NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
              created TEXT NOT NULL, result TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS models(
              id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id),
              name TEXT NOT NULL, path TEXT NOT NULL, created TEXT NOT NULL,
              job TEXT, metadata TEXT NOT NULL DEFAULT '{}');
            """)
            columns={row['name'] for row in db.execute('PRAGMA table_info(images)')}
            if 'deleted' not in columns:db.execute('ALTER TABLE images ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
            if 'group_id' not in columns:db.execute("ALTER TABLE images ADD COLUMN group_id TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / "studio.sqlite", timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def path(self, relative):
        p = (self.root / relative).resolve()
        require(p.is_relative_to(self.root), "invalid_path")
        return p

    @staticmethod
    def decode(row):
        if row is None:
            raise AppError("not_found", status=404)
        value = dict(row)
        for key in ("classes", "boxes", "proposals", "config", "result", "metadata"):
            if key in value:
                value[key] = json.loads(value[key])
        return value

    def get(self, table, identity):
        require(table in {"projects", "images", "jobs", "models"}, "invalid_request")
        with self.db() as db:
            return self.decode(db.execute(f"SELECT * FROM {table} WHERE id=?", (identity,)).fetchone())

    def list(self, table, project=None, include_deleted=False):
        require(table in {"projects", "images", "jobs", "models"}, "invalid_request")
        with self.db() as db:
            sql = f"SELECT * FROM {table}"
            conditions=[]
            if project:conditions.append('project=?')
            if table=='images' and not include_deleted:conditions.append('deleted=0')
            rows = db.execute(sql + (' WHERE '+' AND '.join(conditions) if conditions else '') + " ORDER BY rowid DESC", (project,) if project else ()).fetchall()
            return [self.decode(r) for r in rows]

    def create_project(self, name, station, classes):
        require(isinstance(classes, list) and 0 <= len(classes) <= 200, "invalid_classes")
        require(all(isinstance(c, str) and c.strip() and len(c) <= 80 and not any(ord(x) < 32 for x in c) for c in classes), "invalid_classes")
        classes = [c.strip() for c in classes]
        require(len(set(classes)) == len(classes), "duplicate_classes")
        identity = uid()
        with self.db() as db:
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (identity, safe_name(name), safe_name(station or "default"), json.dumps(classes, ensure_ascii=False), now()))
        return self.get("projects", identity)

    def update_project(self, project_id, name, station=None):
        proj = self.get("projects", project_id)
        new_name = safe_name(name)
        new_station = safe_name(station or "default") if station is not None else proj["station"]
        with self.db() as db:
            db.execute("UPDATE projects SET name=?, station=? WHERE id=?", (new_name, new_station, project_id))
        return self.get("projects", project_id)

    def delete_project(self, project_id):
        self.get("projects", project_id)
        with self.db() as db:
            img_paths = [r["path"] for r in db.execute("SELECT path FROM images WHERE project=?", (project_id,)).fetchall()]
            model_paths = [r["path"] for r in db.execute("SELECT path FROM models WHERE project=?", (project_id,)).fetchall()]
            job_ids = [r["id"] for r in db.execute("SELECT id FROM jobs WHERE project=?", (project_id,)).fetchall()]
            db.execute("DELETE FROM models WHERE project=?", (project_id,))
            db.execute("DELETE FROM jobs WHERE project=?", (project_id,))
            db.execute("DELETE FROM images WHERE project=?", (project_id,))
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        for rel in img_paths:
            try:
                self.path(rel).unlink(missing_ok=True)
            except Exception:
                pass
        shutil.rmtree(self.path(f"images/{project_id}"), ignore_errors=True)
        for jid in job_ids:
            shutil.rmtree(self.path(f"jobs/{jid}"), ignore_errors=True)
        for rel in model_paths:
            try:
                self.path(rel).unlink(missing_ok=True)
            except Exception:
                pass

    def update_project_classes(self, project_id, classes, allow_delete=False):
        require(isinstance(classes,list) and len(classes)<=200,'invalid_classes')
        require(all(isinstance(c,str) and c.strip() and len(c)<=80 and not any(ord(x)<32 for x in c) for c in classes),'invalid_classes')
        classes=[c.strip() for c in classes]
        require(len(set(classes))==len(classes),'duplicate_classes')
        with self.db() as db:
            row=db.execute('SELECT classes FROM projects WHERE id=?',(project_id,)).fetchone()
            require(row is not None,'not_found')
            old=json.loads(row['classes'])
            if not allow_delete:
                require(classes[:len(old)]==old,'classOrderLocked')
            db.execute('UPDATE projects SET classes=? WHERE id=?',(json.dumps(classes,ensure_ascii=False),project_id))
        return self.get('projects',project_id)

    def delete_project_class(self, project_id, class_index):
        proj = self.get('projects', project_id)
        classes = list(proj['classes'])
        require(0 <= class_index < len(classes), 'invalid_classes')
        old_classes = list(classes)
        removed_name = classes.pop(class_index)
        with self.db() as db:
            rows = db.execute("SELECT id, boxes, proposals, revision, status FROM images WHERE project=?", (project_id,)).fetchall()
            for r in rows:
                boxes = json.loads(r['boxes'])
                proposals = json.loads(r['proposals'])
                changed = False
                new_boxes = []
                for b in boxes:
                    if b['class_id'] == class_index:
                        changed = True
                        continue
                    b_copy = dict(b)
                    if b_copy['class_id'] > class_index:
                        b_copy['class_id'] -= 1
                        changed = True
                    new_boxes.append(b_copy)
                new_props = []
                for b in proposals:
                    if b['class_id'] == class_index:
                        changed = True
                        continue
                    b_copy = dict(b)
                    if b_copy['class_id'] > class_index:
                        b_copy['class_id'] -= 1
                        changed = True
                    new_props.append(b_copy)
                if changed:
                    status = r['status']
                    if status == 'reviewed' and not new_boxes:
                        status = 'empty'
                    db.execute(
                        "UPDATE images SET boxes=?, proposals=?, status=?, revision=revision+1 WHERE id=?",
                        (json.dumps(new_boxes), json.dumps(new_props), status, r['id'])
                    )
            db.execute("UPDATE projects SET classes=? WHERE id=?", (json.dumps(classes, ensure_ascii=False), project_id))
        return self.get('projects', project_id)

    def project_summaries(self):
        """Count each project's assets without loading image annotations into the GUI."""
        with self.db() as db:
            rows = db.execute("""
                SELECT p.*, COALESCE(i.image_count,0) AS image_count,
                       COALESCE(i.reviewed_count,0) AS reviewed_count,
                       COALESCE(m.model_count,0) AS model_count
                FROM projects p
                LEFT JOIN (
                    SELECT project, COUNT(*) AS image_count,
                           SUM(status IN ('reviewed','empty')) AS reviewed_count
                    FROM images WHERE deleted=0 GROUP BY project
                ) i ON i.project=p.id
                LEFT JOIN (
                    SELECT project, COUNT(*) AS model_count FROM models GROUP BY project
                ) m ON m.project=p.id
                ORDER BY p.rowid DESC
            """).fetchall()
            return [self.decode(row) for row in rows]

    def import_image(self, project, name, content, boxes=None, status=None):
        proj = self.get("projects", project)
        if boxes is not None:
            boxes = self.validate_boxes(boxes, proj["classes"])
        target_status = status or ("reviewed" if boxes else "unlabeled")
        try:
            with Image.open(io.BytesIO(content)) as source:
                require(source.format in {"JPEG", "PNG", "BMP", "WEBP"}, "invalid_image")
                require(source.width * source.height <= 40_000_000, "image_too_large")
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.load()
        except AppError:
            raise
        except Exception as exc:
            raise AppError("invalid_image", str(exc)) from exc
        # Compare decoded pixels so duplicate files with different metadata stay in one split.
        digest = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        with self.db() as db:
            existing = db.execute("SELECT * FROM images WHERE project=? AND digest=?", (project, digest)).fetchone()
            if existing:
                current = self.decode(existing)
                if existing['deleted']:
                    if boxes is not None and not current['boxes']:
                        db.execute('UPDATE images SET deleted=0,boxes=?,status=?,revision=revision+1 WHERE id=?',(json.dumps(boxes),target_status,existing['id']))
                    else:
                        db.execute('UPDATE images SET deleted=0,revision=revision+1 WHERE id=?',(existing['id'],))
                    return {**self.decode(db.execute('SELECT * FROM images WHERE id=?',(existing['id'],)).fetchone()),'restored':True}
                if boxes and not current['boxes'] and current['status'] in ('unlabeled', 'draft'):
                    db.execute('UPDATE images SET boxes=?,status=?,revision=revision+1 WHERE id=?',(json.dumps(boxes),target_status,existing['id']))
                    return {**self.decode(db.execute('SELECT * FROM images WHERE id=?',(existing['id'],)).fetchone()), "duplicate": True, "annotated": True}
                return {**current, "duplicate": True}
            identity = uid()
            relative = f"images/{project}/{identity}.jpg"
            dest = self.path(relative)
            dest.parent.mkdir(parents=True, exist_ok=True)
            image.save(dest, quality=97)
            db.execute("INSERT INTO images(id,project,name,path,width,height,digest,boxes,status) VALUES(?,?,?,?,?,?,?,?,?)", (identity, project, safe_name(name), relative, image.width, image.height, digest, json.dumps(boxes or []), target_status))
        return self.get("images", identity)

    @staticmethod
    def find_yolo_label(path):
        path = Path(path)
        sidecar = path.with_suffix(".txt")
        if sidecar.is_file() and sidecar.name.lower() != "classes.txt":
            return sidecar
        if path.parent.name.lower() == "images":
            alt = path.parent.parent / "labels" / f"{path.stem}.txt"
            if alt.is_file():
                return alt
        elif path.parent.parent.name.lower() == "images":
            alt = path.parent.parent.parent / "labels" / path.parent.name / f"{path.stem}.txt"
            if alt.is_file():
                return alt
        return None

    @staticmethod
    def parse_yolo_boxes(label_path, class_map):
        if label_path is None or not Path(label_path).is_file():
            return None
        boxes = []
        for line in Path(label_path).read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                raw_cls = int(parts[0])
                cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            except ValueError:
                continue
            if not (0 <= raw_cls < 200 and all(math.isfinite(v) for v in (cx, cy, bw, bh))):
                continue
            x1 = max(0.0, min(1.0, cx - bw / 2.0))
            y1 = max(0.0, min(1.0, cy - bh / 2.0))
            x2 = max(0.0, min(1.0, cx + bw / 2.0))
            y2 = max(0.0, min(1.0, cy + bh / 2.0))
            w, h = x2 - x1, y2 - y1
            if 0 <= x1 < 1 and 0 <= y1 < 1 and w > 0 and h > 0:
                boxes.append({
                    "class_id": class_map.get(raw_cls, raw_cls),
                    "x": x1,
                    "y": y1,
                    "w": w,
                    "h": h,
                })
        return boxes

    def prepare_yolo_import(self, project, paths):
        proj = self.get("projects", project)
        folder_classes = []
        seen_dirs = set()
        for raw in paths:
            p = Path(raw)
            for d in (p.parent, p.parent.parent):
                if d in seen_dirs or not d.is_dir():
                    continue
                seen_dirs.add(d)
                cf = d / "classes.txt"
                if cf.is_file():
                    for line in cf.read_text(encoding="utf-8", errors="replace").splitlines():
                        cname = line.strip()
                        if cname and len(cname) <= 80 and not any(ord(x) < 32 for x in cname) and cname not in folder_classes:
                            folder_classes.append(cname)
        referenced_ids = set()
        label_files = {}
        for raw in paths:
            p = Path(raw)
            lf = self.find_yolo_label(p)
            if lf is not None:
                label_files[p] = lf
                for line in lf.read_text(encoding="utf-8", errors="replace").splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        try:
                            cid = int(parts[0])
                            if 0 <= cid < 200:
                                referenced_ids.add(cid)
                        except ValueError:
                            pass
        current = list(proj["classes"])
        class_map = {}
        all_ids = sorted(referenced_ids | set(range(len(folder_classes))))
        for cid in all_ids:
            if cid < len(folder_classes):
                cname = folder_classes[cid]
                if cname not in current and len(current) < 200:
                    current.append(cname)
                class_map[cid] = current.index(cname) if cname in current else cid
            elif cid < len(current):
                class_map[cid] = cid
            else:
                while len(current) <= cid and len(current) < 200:
                    fallback = f"class_{len(current)}"
                    while fallback in current:
                        fallback += "_"
                    current.append(fallback)
                class_map[cid] = cid
        if current != proj["classes"]:
            self.update_project_classes(project, current)
        return label_files, class_map

    def validate_boxes(self, boxes, classes):
        require(isinstance(boxes, list) and len(boxes) <= 10000, "invalid_boxes")
        result = []
        for box in boxes:
            require(isinstance(box, dict), "invalid_boxes")
            cls = box.get("class_id")
            require(type(cls) is int and 0 <= cls < len(classes), "invalid_classes")
            coords = [box.get(k) for k in ("x", "y", "w", "h")]
            require(all(type(n) in (int, float) and math.isfinite(n) for n in coords), "invalid_boxes")
            x, y, w, h = coords
            require(0 <= x < 1 and 0 <= y < 1 and w > 0 and h > 0 and x + w <= 1.000001 and y + h <= 1.000001, "invalid_boxes")
            result.append({"class_id": cls, "x": x, "y": y, "w": w, "h": h})
        return result

    def save_image(self, identity, boxes, revision, reviewed=False, excluded=False, proposals_handled=False):
        image = self.get("images", identity)
        require(not image['deleted'],'image_removed')
        project = self.get("projects", image["project"])
        boxes = self.validate_boxes(boxes, project["classes"])
        status = "excluded" if excluded else (("reviewed" if boxes else "empty") if reviewed else ("pending" if image["status"] == "pending" and not proposals_handled else "draft"))
        proposals = [] if reviewed or excluded or proposals_handled else image["proposals"]
        with self.db() as db:
            cursor = db.execute("UPDATE images SET boxes=?, proposals=?, status=?,revision=revision+1 WHERE id=? AND revision=?", (json.dumps(boxes), json.dumps(proposals), status, identity, revision))
            require(cursor.rowcount == 1, "revision_conflict", status=409)
        return self.get("images", identity)

    def trash_images(self,project,identities,deleted=True):
        require(isinstance(identities,list) and bool(identities),'no_selection')
        identities=list(dict.fromkeys(identities))
        with self.db() as db:
            for identity in identities:
                row=db.execute('SELECT project FROM images WHERE id=?',(identity,)).fetchone()
                require(row is not None and row['project']==project,'not_found')
            for identity in identities:
                db.execute('UPDATE images SET deleted=?,revision=revision+1 WHERE id=? AND deleted!=?',(int(deleted),identity,int(deleted)))
        return len(identities)

    def audit_images(self,project):
        problems=[]
        images=self.list('images',project)
        for image in images:
            try:
                with Image.open(self.path(image['path'])) as source:
                    source.load()
                    require(source.size==(image['width'],image['height']),'invalid_image')
            except Exception as exc:problems.append({'id':image['id'],'name':image['name'],'detail':str(exc)})
        return {'total':len(images),'valid':len(images)-len(problems),'problems':problems}

    def prepare_image(self,identity,operation,options=None):
        """Preview transformations and transform labels in normalized coordinates."""
        options=options or {};source=self.get('images',identity);require(not source['deleted'],'image_removed')
        with Image.open(self.path(source['path'])) as opened:image=opened.convert('RGB')
        boxes=json.loads(json.dumps(source['boxes']))
        if operation=='rotate':
            image=image.transpose(Image.Transpose.ROTATE_270)
            boxes=[{**b,'x':1-b['y']-b['h'],'y':b['x'],'w':b['h'],'h':b['w']} for b in boxes]
        elif operation=='flip':
            image=ImageOps.mirror(image);boxes=[{**b,'x':1-b['x']-b['w']} for b in boxes]
        elif operation=='grayscale':image=ImageOps.grayscale(image).convert('RGB')
        elif operation=='autocontrast':image=ImageOps.autocontrast(image)
        elif operation=='brightness':
            factor=options.get('factor',1.2);require(type(factor) in (int,float) and .2<=factor<=3,'invalid_parameters');image=ImageEnhance.Brightness(image).enhance(factor)
        elif operation=='resize':
            edge=options.get('edge',1024);require(type(edge) is int and 64<=edge<=8192,'invalid_parameters')
            scale=edge/max(image.size);size=tuple(max(1,round(n*scale)) for n in image.size);require(size[0]*size[1]<=40_000_000,'image_too_large');image=image.resize(size,Image.Resampling.LANCZOS)
        elif operation=='crop':
            x,y,w,h=[options.get(k) for k in ('x','y','w','h')]
            require(all(type(n) is int for n in (x,y,w,h)) and x>=0 and y>=0 and w>0 and h>0 and x+w<=image.width and y+h<=image.height,'invalid_crop')
            iw,ih=image.size;transformed=[]
            for b in boxes:
                x1=max(x,b['x']*iw);y1=max(y,b['y']*ih);x2=min(x+w,(b['x']+b['w'])*iw);y2=min(y+h,(b['y']+b['h'])*ih)
                if x2>x1 and y2>y1:transformed.append({'class_id':b['class_id'],'x':(x1-x)/w,'y':(y1-y)/h,'w':(x2-x1)/w,'h':(y2-y1)/h})
            boxes=transformed;image=image.crop((x,y,x+w,y+h))
        else:raise AppError('invalid_request')
        for b in boxes:
            b['x']=max(0.,b['x']);b['y']=max(0.,b['y']);b['w']=min(1-b['x'],b['w']);b['h']=min(1-b['y'],b['h'])
        return image,boxes,source

    def process_image(self,identity,operation,options=None):
        image,boxes,source=self.prepare_image(identity,operation,options)
        digest=hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
        with self.db() as db:
            existing=db.execute('SELECT * FROM images WHERE project=? AND digest=?',(source['project'],digest)).fetchone()
            if existing:
                if existing['deleted']:
                    db.execute('UPDATE images SET deleted=0,revision=revision+1 WHERE id=?',(existing['id'],))
                    return {**self.decode(db.execute('SELECT * FROM images WHERE id=?',(existing['id'],)).fetchone()),'restored':True}
                return {**self.decode(existing),'duplicate':True}
            new_id=uid();relative=f"images/{source['project']}/{new_id}.png";image.save(self.path(relative),'PNG')
            group=source['group_id'] or source['digest']
            db.execute("UPDATE images SET group_id=? WHERE id=?",(group,identity))
            db.execute("INSERT INTO images(id,project,name,path,width,height,digest,boxes,status,group_id) VALUES(?,?,?,?,?,?,?,?,?,?)",(new_id,source['project'],safe_name(Path(source['name']).stem+'_'+operation+'.png'),relative,image.width,image.height,digest,json.dumps(boxes),'draft',group))
        return self.get('images',new_id)

    def create_job(self, project, kind, config):
        self.get("projects", project)
        identity = uid()
        with self.db() as db:
            require(not db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone(), "job_busy", status=409)
            db.execute("INSERT INTO jobs(id,project,kind,status,config,created) VALUES(?,?,?,'queued',?,?)", (identity, project, kind, json.dumps(config), now()))
        self.path(f"jobs/{identity}").mkdir(parents=True, exist_ok=True)
        return self.get("jobs", identity)

    def update_job(self, identity, **values):
        require(set(values) <= {"status", "progress", "message", "result"}, "invalid_request")
        if "result" in values:
            values["result"] = json.dumps(values["result"], ensure_ascii=False)
        with self.db() as db:
            db.execute("UPDATE jobs SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?", (*values.values(), identity))

    def snapshot(self, project_id, destination):
        project = self.get("projects", project_id)
        images = [im for im in self.list("images", project_id) if im["status"] in ("reviewed", "empty")]
        require(len(images) >= 3, "need_reviewed_images")
        require(any(im["boxes"] for im in images), "need_positive_labels")
        # Originals and processed copies must never cross dataset partitions.
        groups={}
        for im in images:groups.setdefault(im['group_id'] or im['digest'],[]).append(im)
        require(len(groups)>=3,'need_source_groups')
        ordered=sorted(groups,key=lambda key:hashlib.sha256(('split-v1'+key).encode()).hexdigest())
        n=len(ordered);val_count,test_count=max(1,round(n*.2)),max(1,round(n*.1))
        splits=['val']*val_count+['test']*test_count+['train']*(n-val_count-test_count)
        positive=next(i for i,key in enumerate(ordered) if any(im['boxes'] for im in groups[key]))
        if not any(im['boxes'] for key,split in zip(ordered,splits) if split=='train' for im in groups[key]):
            j=splits.index('train');ordered[positive],ordered[j]=ordered[j],ordered[positive]
        images=[im for key in ordered for im in groups[key]]
        assignments=[split for key,split in zip(ordered,splits) for im in groups[key]]
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=False)
        manifest = {"project": project, "created": now(), "split_seed": "split-v1", "grouping": "source-family", "images": [], "counts": {"train": 0, "val": 0, "test": 0}}
        for im, split in zip(images, assignments):
            image_dir, label_dir = dest / "images" / split, dest / "labels" / split
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.path(im["path"]), image_dir / (im["id"] + Path(im['path']).suffix))
            lines = [f"{b['class_id']} {b['x']+b['w']/2:.8f} {b['y']+b['h']/2:.8f} {b['w']:.8f} {b['h']:.8f}" for b in im["boxes"]]
            (label_dir / (im["id"] + ".txt")).write_text("\n".join(lines), encoding="utf-8")
            manifest["images"].append({"id": im["id"], "name": im["name"], "digest": im["digest"], "revision": im["revision"], "group_id": im['group_id'] or im['digest'], "split": split})
            manifest["counts"][split] += 1
        yaml = f"path: {json.dumps(dest.resolve().as_posix(), ensure_ascii=False)}\ntrain: images/train\nval: images/val\ntest: images/test\nnames: {json.dumps(project['classes'], ensure_ascii=False)}\n"
        (dest / "data.yaml").write_text(yaml, encoding="utf-8")
        (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def register_model(self, project, name, path, job=None, metadata=None):
        self.get("projects", project)
        identity = uid()
        relative = Path(path).resolve().relative_to(self.root).as_posix()
        with self.db() as db:
            db.execute("INSERT INTO models VALUES(?,?,?,?,?,?,?)", (identity, project, safe_name(name), relative, now(), job, json.dumps(metadata or {}, ensure_ascii=False)))
        return self.get("models", identity)

    def model_package(self, identity, name):
        model = self.get("models", identity)
        project = self.get("projects", model["project"])
        name = safe_name(name)
        target = self.path(f"exports/{uid()}/{name}.zip")
        target.parent.mkdir(parents=True, exist_ok=True)
        metadata = {**model, "export_name": name, "exported": now(), "project": project}
        # An imported model does not inherit project class IDs until inspected by YOLO.
        classes = model["metadata"].get("classes")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(self.path(model["path"]), f"{name}.pt")
            z.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
            if classes is not None:
                z.writestr("classes.json", json.dumps(classes, ensure_ascii=False, indent=2))
            if model["job"]:
                job = self.get("jobs", model["job"])
                z.writestr("training.json", json.dumps(job, ensure_ascii=False, indent=2))
                job_dir = self.path(f"jobs/{model['job']}")
                for filename in ("dataset/manifest.json", "run/results.csv", "run/results.png", "run/confusion_matrix.png", "run/args.yaml"):
                    f = job_dir / filename
                    if f.is_file():
                        z.write(f, filename)
            z.writestr("README.txt", "YOLO Studio model package\nThe .pt file is an Ultralytics detection model.\nSee metadata.json for model provenance and class information.\n")
        return target
