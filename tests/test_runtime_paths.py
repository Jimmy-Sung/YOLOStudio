import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_paths


class RuntimePathTests(unittest.TestCase):
    def test_installed_data_does_not_write_to_program_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(runtime_paths,'distribution_info',return_value={'profile':'cpu'}),patch.dict(os.environ,{'LOCALAPPDATA':folder}):
                with patch.dict(os.environ,clear=False):
                    os.environ.pop('YOLO_STUDIO_DATA',None)
                    self.assertEqual(runtime_paths.default_data_dir(),Path(folder)/'YOLOStudio/data')

    def test_explicit_data_override(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'YOLO_STUDIO_DATA':folder}):
            self.assertEqual(runtime_paths.default_data_dir(),Path(folder).resolve())

    def test_weights_use_read_only_bundle_before_writable_cache(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);app=base/'app';weights=app/'models/yolo11n.pt';weights.parent.mkdir(parents=True);weights.write_bytes(b'fixture')
            with patch.object(runtime_paths,'APP_ROOT',app):
                self.assertEqual(runtime_paths.pretrained_path('yolo11n.pt',base/'data'),weights)
                cached=runtime_paths.pretrained_path('yolo11s.pt',base/'data')
                self.assertEqual(cached,base/'data/runtime/weights/yolo11s.pt')
                self.assertTrue(cached.parent.is_dir())
