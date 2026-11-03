import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from core import Store, AppError


class ProjectClassTests(unittest.TestCase):
    def test_deferred_classes_and_stable_ids(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d));p=store.create_project('DIP','',[])
            self.assertEqual(p['classes'],[])
            store.update_project_classes(p['id'],['screw'])
            store.update_project_classes(p['id'],['screw','cap'])
            with self.assertRaises(AppError):store.update_project_classes(p['id'],['cap','screw'])
            with self.assertRaises(AppError):store.update_project_classes(p['id'],['screw'])
            with self.assertRaises(AppError):store.update_project_classes(p['id'],['screw','screw'])
            self.assertEqual(store.get('projects',p['id'])['classes'],['screw','cap'])

    def test_yolo_txt_and_classes_txt_auto_import_and_backfill(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            store = Store(root / 'store')
            proj = store.create_project('DI_AOI', 'DIP', [])
            src = root / 'originSize'
            src.mkdir()
            img_path = src / 'sample1.jpg'
            buf = io.BytesIO()
            Image.new('RGB', (400, 200), '#112233').save(buf, format='JPEG')
            img_bytes = buf.getvalue()
            img_path.write_bytes(img_bytes)
            im0 = store.import_image(proj['id'], img_path.name, img_bytes)
            self.assertEqual(im0['boxes'], [])
            self.assertEqual(im0['status'], 'unlabeled')
            (src / 'classes.txt').write_text('Solder Joint\n', encoding='utf-8')
            (src / 'sample1.txt').write_text('0 0.5 0.5 0.2 0.4\n', encoding='utf-8')
            labels, cmap = store.prepare_yolo_import(proj['id'], [img_path])
            self.assertEqual(store.get('projects', proj['id'])['classes'], ['Solder Joint'])
            boxes = store.parse_yolo_boxes(labels.get(img_path), cmap)
            im1 = store.import_image(proj['id'], img_path.name, img_bytes, boxes=boxes)
            self.assertTrue(im1.get('annotated'))
            self.assertEqual(im1['status'], 'reviewed')
            self.assertEqual(len(im1['boxes']), 1)
            self.assertEqual(im1['boxes'][0]['class_id'], 0)
            self.assertAlmostEqual(im1['boxes'][0]['x'], 0.4)
            self.assertAlmostEqual(im1['boxes'][0]['y'], 0.3)
            self.assertAlmostEqual(im1['boxes'][0]['w'], 0.2)
            self.assertAlmostEqual(im1['boxes'][0]['h'], 0.4)

    def test_delete_project_class_and_box_remapping(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            store = Store(root / 'store')
            proj = store.create_project('P1', 'ST', ['c0', 'c1', 'c2'])
            buf = io.BytesIO()
            Image.new('RGB', (100, 100), '#555555').save(buf, format='JPEG')
            im = store.import_image(proj['id'], 'test.jpg', buf.getvalue(), boxes=[
                {'class_id': 0, 'x': 0.1, 'y': 0.1, 'w': 0.2, 'h': 0.2},
                {'class_id': 1, 'x': 0.3, 'y': 0.3, 'w': 0.2, 'h': 0.2},
                {'class_id': 2, 'x': 0.5, 'y': 0.5, 'w': 0.2, 'h': 0.2},
            ])
            self.assertEqual(len(im['boxes']), 3)
            # Delete class index 1 ('c1')
            store.delete_project_class(proj['id'], 1)
            p_updated = store.get('projects', proj['id'])
            self.assertEqual(p_updated['classes'], ['c0', 'c2'])
            im_updated = store.get('images', im['id'])
            self.assertEqual(len(im_updated['boxes']), 2)
            self.assertEqual(im_updated['boxes'][0]['class_id'], 0)
            self.assertEqual(im_updated['boxes'][1]['class_id'], 1) # was 2, shifted to 1

