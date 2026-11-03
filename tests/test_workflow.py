import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from core import AppError, Store


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.project = self.store.create_project('產品A', 'ST02', ['screw', 'NOPASS'])

    def tearDown(self):
        self.temp.cleanup()

    def image(self, color, name='image.png'):
        content = io.BytesIO()
        Image.new('RGB', (100, 80), color).save(content, format='PNG')
        return self.store.import_image(self.project['id'], name, content.getvalue())

    def box(self):
        return {'class_id': 0, 'x': .1, 'y': .2, 'w': .4, 'h': .3}

    def test_duplicate_pixels_and_invalid_images(self):
        first = self.image('red')
        duplicate = self.image('red', 'renamed.png')
        self.assertEqual(first['id'], duplicate['id'])
        self.assertTrue(duplicate['duplicate'])
        with self.assertRaises(AppError):
            self.store.import_image(self.project['id'], 'bad.png', b'not an image')

    def test_revision_protection_and_box_validation(self):
        im = self.image('red')
        saved = self.store.save_image(im['id'], [self.box()], 0, reviewed=True)
        self.assertEqual(saved['status'], 'reviewed')
        with self.assertRaisesRegex(AppError, 'revision_conflict'):
            self.store.save_image(im['id'], [], 0)
        for box in [{**self.box(), 'class_id': 3}, {**self.box(), 'w': 1}, {**self.box(), 'x': float('nan')}]:
            with self.assertRaises(AppError):
                self.store.save_image(im['id'], [box], saved['revision'])

    def test_suggestions_remain_pending_until_human_review(self):
        im = self.image('red')
        with self.store.db() as db:
            db.execute("UPDATE images SET proposals=?,status='pending' WHERE id=?", (json.dumps([self.box()]), im['id']))
        draft = self.store.save_image(im['id'], [self.box()], 0)
        self.assertEqual(draft['status'], 'pending')
        self.assertEqual(len(draft['proposals']), 1)
        reviewed = self.store.save_image(im['id'], [self.box()], 1, reviewed=True)
        self.assertEqual(reviewed['status'], 'reviewed')
        self.assertEqual(reviewed['proposals'], [])

    def test_snapshot_excludes_unreviewed_and_preserves_class_ids(self):
        originals = []
        for color in ['red', 'green', 'blue', 'yellow']:
            im = self.image(color)
            originals.append(im)
            self.store.save_image(im['id'], [self.box()] if color == 'red' else [], 0, reviewed=True)
        unreviewed = self.image('black')
        snap = Path(self.temp.name) / 'snapshot'
        manifest = self.store.snapshot(self.project['id'], snap)
        self.assertEqual(sum(manifest['counts'].values()), 4)
        self.assertNotIn(unreviewed['id'], [x['id'] for x in manifest['images']])
        self.assertEqual(manifest['project']['classes'], ['screw', 'NOPASS'])
        train = list((snap/'labels/train').glob('*.txt'))
        self.assertTrue(any(p.read_text().startswith('0 0.30000000 0.35000000 0.40000000 0.30000000') for p in train))
        # Changes after a run starts must not mutate its snapshot labels.
        first = self.store.get('images', originals[0]['id'])
        self.store.save_image(first['id'], [], first['revision'], reviewed=True)
        self.assertTrue(any(p.read_text() for p in train))

    def test_training_guardrails_and_traversal(self):
        with self.assertRaisesRegex(AppError, 'need_reviewed_images'):
            self.store.snapshot(self.project['id'], Path(self.temp.name)/'small')
        for color in ['red', 'green', 'blue']:
            im = self.image(color)
            self.store.save_image(im['id'], [], 0, reviewed=True)
        with self.assertRaisesRegex(AppError, 'need_positive_labels'):
            self.store.snapshot(self.project['id'], Path(self.temp.name)/'empty')
        with self.assertRaisesRegex(AppError, 'invalid_path'):
            self.store.path('../escape')

    def test_export_names_do_not_overwrite_and_include_provenance(self):
        weights = self.store.path('models/test.pt')
        weights.parent.mkdir(parents=True)
        weights.write_bytes(b'test weights; package-only test')
        model = self.store.register_model(self.project['id'], '測試模型', weights, metadata={'classes': ['screw', 'NOPASS']})
        first = self.store.model_package(model['id'], '產品A_v001')
        second = self.store.model_package(model['id'], '產品A_v001')
        self.assertNotEqual(first, second)
        with zipfile.ZipFile(first) as z:
            self.assertIn('產品A_v001.pt', z.namelist())
            self.assertEqual(json.loads(z.read('classes.json')), ['screw', 'NOPASS'])
            self.assertEqual(json.loads(z.read('metadata.json'))['project']['name'], '產品A')

    def test_only_one_background_job_can_run(self):
        self.store.create_job(self.project['id'], 'train', {})
        with self.assertRaisesRegex(AppError, 'job_busy'):
            self.store.create_job(self.project['id'], 'autolabel', {})

    def test_project_home_counts_are_separate_and_refresh_after_review(self):
        other=self.store.create_project('產品B','ST03',['cap'])
        im=self.image('red')
        before={p['id']:p for p in self.store.project_summaries()}
        self.assertEqual(before[self.project['id']]['image_count'],1)
        self.assertEqual(before[self.project['id']]['reviewed_count'],0)
        self.store.save_image(im['id'],[self.box()],0,reviewed=True)
        weights=self.store.path('model.pt');weights.write_bytes(b'count-only fixture')
        for i in range(2):self.store.register_model(self.project['id'],f'v{i}',weights)
        after={p['id']:p for p in self.store.project_summaries()}
        self.assertEqual(after[self.project['id']]['image_count'],1)
        self.assertEqual(after[self.project['id']]['reviewed_count'],1)
        self.assertEqual(after[self.project['id']]['model_count'],2)
        self.assertEqual(after[other['id']]['image_count'],0)
        self.assertEqual(after[other['id']]['model_count'],0)

    def test_trash_restores_annotations_and_reimport_restores_same_image(self):
        im=self.image('red');saved=self.store.save_image(im['id'],[self.box()],0,reviewed=True)
        self.store.trash_images(self.project['id'],[im['id']])
        self.assertEqual(self.store.list('images',self.project['id']),[])
        self.assertEqual(len(self.store.list('images',self.project['id'],include_deleted=True)),1)
        self.assertTrue(self.store.path(im['path']).is_file())
        with self.assertRaisesRegex(AppError,'image_removed'):self.store.save_image(im['id'],[],saved['revision'])
        restored=self.image('red')
        self.assertEqual(restored['id'],im['id']);self.assertTrue(restored['restored'])
        self.assertEqual(restored['boxes'],[self.box()]);self.assertEqual(restored['status'],'reviewed')

    def test_preprocessing_preserves_original_and_transforms_boxes(self):
        im=self.image('red');self.store.save_image(im['id'],[self.box()],0,reviewed=True)
        original=self.store.path(im['path']).read_bytes()
        rotated=self.store.process_image(im['id'],'rotate')
        self.assertEqual((rotated['width'],rotated['height']),(80,100));self.assertEqual(rotated['status'],'draft')
        self.assertAlmostEqual(rotated['boxes'][0]['x'],.5);self.assertAlmostEqual(rotated['boxes'][0]['y'],.1)
        flipped=self.store.process_image(im['id'],'flip');self.assertAlmostEqual(flipped['boxes'][0]['x'],.5)
        resized=self.store.process_image(im['id'],'resize',{'edge':200});self.assertEqual((resized['width'],resized['height']),(200,160));self.assertEqual(resized['boxes'],[self.box()])
        crop=self.store.process_image(im['id'],'crop',{'x':20,'y':16,'w':30,'h':24})
        self.assertAlmostEqual(crop['boxes'][0]['x'],0);self.assertAlmostEqual(crop['boxes'][0]['w'],1)
        self.assertEqual(self.store.path(im['path']).read_bytes(),original)
        self.assertEqual(rotated['group_id'],im['digest'])
        with self.assertRaisesRegex(AppError,'invalid_crop'):self.store.process_image(im['id'],'crop',{'x':90,'y':0,'w':30,'h':10})

    def test_processed_copies_stay_with_source_in_dataset_split(self):
        original=None
        for color in ['red','green','blue']:
            im=self.image(color);self.store.save_image(im['id'],[self.box()],0,reviewed=True)
            if original is None:original=im
        child=self.store.process_image(original['id'],'rotate');self.store.save_image(child['id'],child['boxes'],child['revision'],reviewed=True)
        manifest=self.store.snapshot(self.project['id'],Path(self.temp.name)/'grouped')
        rows={im['id']:im for im in manifest['images']}
        self.assertEqual(rows[child['id']]['split'],rows[original['id']]['split'])
        exported=Path(self.temp.name)/'grouped/images'/rows[child['id']]['split']/(child['id']+'.png')
        with Image.open(exported) as image:self.assertEqual(image.format,'PNG')

    def test_copies_do_not_count_as_independent_training_sources(self):
        im=self.image('red');self.store.save_image(im['id'],[self.box()],0,reviewed=True)
        for operation,options in [('rotate',{}),('grayscale',{}),('resize',{'edge':200})]:
            child=self.store.process_image(im['id'],operation,options);self.store.save_image(child['id'],child['boxes'],child['revision'],reviewed=True)
        with self.assertRaisesRegex(AppError,'need_source_groups'):self.store.snapshot(self.project['id'],Path(self.temp.name)/'one-source')

    def test_image_audit_reports_corrupt_files(self):
        im=self.image('red');self.store.path(im['path']).write_bytes(b'corrupt')
        result=self.store.audit_images(self.project['id'])
        self.assertEqual(result['valid'],0);self.assertEqual(result['problems'][0]['id'],im['id'])

    def test_existing_database_migration_keeps_images(self):
        im=self.image('red')
        with self.store.db() as db:
            db.execute('ALTER TABLE images DROP COLUMN deleted');db.execute('ALTER TABLE images DROP COLUMN group_id')
        migrated=Store(self.temp.name);retained=migrated.get('images',im['id'])
        self.assertEqual(retained['name'],im['name']);self.assertEqual(retained['deleted'],0);self.assertEqual(retained['group_id'],'')


if __name__ == '__main__':
    unittest.main()
