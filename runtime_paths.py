"""Separate read-only application resources from writable user data."""
import json
import os
from pathlib import Path

APP_ROOT=Path(__file__).resolve().parent


def distribution_info():
    path=APP_ROOT.parent/'distribution.json'
    if not path.is_file():return {}
    return json.loads(path.read_text(encoding='utf-8'))


def default_data_dir():
    override=os.environ.get('YOLO_STUDIO_DATA')
    if override:return Path(override).expanduser().resolve()
    if distribution_info():
        return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'YOLOStudio'/'data'
    return APP_ROOT/'data'


def pretrained_path(name,data_root):
    bundled=APP_ROOT/'models'/name
    if bundled.is_file():return bundled
    cached=Path(data_root)/'runtime'/'weights'/name
    cached.parent.mkdir(parents=True,exist_ok=True)
    return cached
