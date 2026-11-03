"""Native widget tests. Offscreen events never control the user's desktop."""
import io
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PIL import Image
from PySide6.QtCore import QPoint,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QLineEdit,QPlainTextEdit,QMessageBox
from core import Store
from desktop import MainWindow
from jobs import JobManager

APP=QApplication.instance() or QApplication([])


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name)
        self.project=self.store.create_project('原生測試','ST01',['screw','NOPASS'])
        content=io.BytesIO();Image.new('RGB',(640,480),'#245744').save(content,format='PNG')
        self.image=self.store.import_image(self.project['id'],'sample.png',content.getvalue())
        self.manager=JobManager(self.store)
        self.window=MainWindow(self.store,self.manager)
        self.window.timer.stop();self.errors=[];self.window.error=self.errors.append
        self.window.show();APP.processEvents()

    def tearDown(self):
        self.window.close();APP.processEvents()
        self.assertEqual(self.errors,[])
        self.temp.cleanup()

    def draw_box(self):
        self.window.go(1);APP.processEvents();canvas=self.window.canvas;r=canvas.image_rect()
        a=QPoint(round(r.x()+r.width()*.2),round(r.y()+r.height()*.2));b=QPoint(round(r.x()+r.width()*.6),round(r.y()+r.height()*.6))
        QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(canvas,b);QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=b);APP.processEvents()

    def test_native_drawing_save_review_and_undo(self):
        self.draw_box()
        self.assertEqual(len(self.window.canvas.boxes),1)
        self.assertTrue(self.window.dirty)
        self.window.save_draft()
        saved=self.store.get('images',self.image['id']);self.assertEqual(saved['status'],'draft')
        self.assertAlmostEqual(saved['boxes'][0]['x'],.2,places=2)
        self.window.review();self.assertEqual(self.store.get('images',self.image['id'])['status'],'reviewed')
        self.window.canvas.undo();self.assertEqual(len(self.window.canvas.boxes),0)
        self.window.save_draft();self.assertEqual(self.store.get('images',self.image['id'])['status'],'draft')

    def test_language_switch_and_preference_persistence(self):
        for index,expected in [(0,'圖片與標註'),(1,'图片与标注'),(2,'Images & labels')]:
            self.window.language.setCurrentIndex(index);APP.processEvents();self.assertEqual(self.window.nav[1].text().replace('&&','&'),expected)
            self.assertEqual(self.window.project()['classes'],['screw','NOPASS'])
        self.assertIn('"en"',Path(self.temp.name,'preferences.json').read_text())

    def test_selection_resize_and_class_assignment(self):
        self.draw_box();canvas=self.window.canvas;self.window.set_mode('select');rect=canvas.box_rect(canvas.boxes[0]);a=rect.center().toPoint();b=a+QPoint(15,10)
        QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(canvas,b);QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=b)
        self.assertGreater(canvas.boxes[0]['x'],.2)
        rect=canvas.box_rect(canvas.boxes[0]);a=rect.bottomRight().toPoint();b=a+QPoint(20,15)
        QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(canvas,b);QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=b)
        self.assertGreater(canvas.boxes[0]['w'],.4)
        self.window.box_class.setCurrentIndex(1);self.assertEqual(canvas.boxes[0]['class_id'],1)
        canvas.delete_selected();self.assertEqual(canvas.boxes,[])

    def test_resize_any_edge_in_draw_mode_and_move_selected(self):
        self.draw_box();canvas=self.window.canvas;self.assertEqual(self.window.canvas.mode,'draw')
        original=dict(canvas.boxes[0])
        def drag(a,b):
            QTest.mousePress(canvas,Qt.MouseButton.LeftButton,pos=a);QTest.mouseMove(canvas,b);QTest.mouseRelease(canvas,Qt.MouseButton.LeftButton,pos=b);APP.processEvents()
        rect=canvas.box_rect(canvas.boxes[0])
        # Left edge outward: x decreases, width grows, still one box (no new box drawn).
        a=QPoint(round(rect.left()),round(rect.center().y()));drag(a,a-QPoint(30,0))
        self.assertEqual(len(canvas.boxes),1);self.assertLess(canvas.boxes[0]['x'],original['x']);self.assertGreater(canvas.boxes[0]['w'],original['w'])
        # Top-left corner inward.
        rect=canvas.box_rect(canvas.boxes[0]);before=dict(canvas.boxes[0]);a=rect.topLeft().toPoint();drag(a,a+QPoint(20,20))
        self.assertGreater(canvas.boxes[0]['y'],before['y']);self.assertLess(canvas.boxes[0]['h'],before['h'])
        # Dragging inside the selected box moves it in draw mode.
        rect=canvas.box_rect(canvas.boxes[0]);before=dict(canvas.boxes[0]);a=rect.center().toPoint();drag(a,a+QPoint(10,10))
        self.assertEqual(len(canvas.boxes),1);self.assertGreater(canvas.boxes[0]['x'],before['x']);self.assertAlmostEqual(canvas.boxes[0]['w'],before['w'])
        canvas.undo();self.assertAlmostEqual(canvas.boxes[0]['x'],before['x'])

    def test_project_cards_switch_and_save_work_without_mixing_projects(self):
        other=self.store.create_project('第二個產品','ST02',['cap'])
        self.window.refresh();APP.processEvents()
        self.assertEqual(len(self.window.project_tiles),2)
        self.assertTrue(self.window.project_tiles[self.project['id']].property('active'))
        self.draw_box();self.assertTrue(self.window.dirty)
        self.window.select_project_card(other['id'])
        self.assertEqual(self.store.get('images',self.image['id'])['status'],'draft')
        self.assertEqual(self.window.project_select.currentData(),other['id'])
        self.assertEqual(self.window.images,[])
        self.assertEqual(self.window.canvas.boxes,[])
        self.assertTrue(self.window.project_tiles[other['id']].property('active'))
        self.assertFalse(self.window.project_tiles[self.project['id']].property('active'))
        self.assertIn(other['id'],Path(self.temp.name,'preferences.json').read_text())
        self.window.go(4);APP.processEvents()
        QTest.mouseClick(self.window.project_tiles[self.project['id']],Qt.MouseButton.LeftButton,pos=QPoint(12,12));APP.processEvents()
        self.assertEqual(self.window.project_id,self.project['id'])
        self.assertEqual(self.window.stack.currentIndex(),0)
        self.window.home_button.click();APP.processEvents()
        self.assertEqual(self.window.stack.currentIndex(),4)
        QTest.mouseClick(self.window.project_card_buttons[self.project['id']],Qt.MouseButton.LeftButton);APP.processEvents()
        self.assertEqual(self.window.stack.currentIndex(),0)
        self.window.nav[1].click();APP.processEvents()
        self.assertEqual(self.window.stack.currentIndex(),1)
        self.assertEqual(self.window.current['id'],self.image['id'])
        # Polling unchanged data must not rebuild cards or discard keyboard focus.
        tile=self.window.project_tiles[self.project['id']];self.window.refresh()
        self.assertIs(tile,self.window.project_tiles[self.project['id']])

    def test_new_project_tile_creates_and_selects_a_project(self):
        callback_errors=[]
        def complete_dialog():
            try:
                dialog=APP.activeModalWidget()
                fields=dialog.findChildren(QLineEdit)
                fields[0].setText('首頁新增專案');fields[1].setText('ST03')
                dialog.findChild(QPlainTextEdit).setPlainText('cap\nfinish')
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
            except Exception as exc:
                callback_errors.append(exc)
                if APP.activeModalWidget():APP.activeModalWidget().reject()
        QTimer.singleShot(0,complete_dialog)
        QTest.mouseClick(self.window.new_project_tile,Qt.MouseButton.LeftButton);APP.processEvents()
        self.assertEqual(callback_errors,[])
        self.assertEqual(self.window.project()['name'],'首頁新增專案')
        self.assertEqual(self.window.project()['classes'],['cap','finish'])
        self.assertEqual(len(self.window.project_tiles),2)
        self.assertTrue(self.window.project_tiles[self.window.project_id].property('active'))
        self.assertEqual(self.window.stack.currentIndex(),0)

    def test_project_gallery_is_a_separate_first_level(self):
        self.assertEqual(self.window.stack.currentIndex(),4)
        self.assertTrue(self.window.new_project_button.isVisible())
        self.assertTrue(self.window.new_project_tile.isVisible())
        self.assertTrue(self.window.project_tiles[self.project['id']].isVisible())
        self.assertFalse(self.window.stat_labels[0].isVisible())
        self.assertFalse(self.window.info_label.isVisible())
        self.assertTrue(all(not button.isVisible() for button in self.window.nav))
        self.assertFalse(self.window.dataset_nav.isVisible())
        self.assertEqual(self.window.project_title.text(),self.window.tr('allProjects'))
        self.window.project_card_buttons[self.project['id']].click();APP.processEvents()
        self.assertEqual(self.window.stack.currentIndex(),0)
        self.assertFalse(self.window.new_project_button.isVisible())
        self.assertTrue(self.window.stat_labels[0].isVisible())
        self.assertTrue(self.window.info_label.isVisible())
        self.assertFalse(self.window.project_tiles[self.project['id']].isVisible())
        self.assertTrue(all(button.isVisible() for button in self.window.nav))
        for page in (1,2,3,5):
            self.window.go(page);APP.processEvents()
            self.assertFalse(self.window.new_project_button.isVisible())
        self.assertEqual(self.window.project_title.text(),self.project['name'])
        self.window.home_button.click();APP.processEvents()
        self.assertEqual(self.window.stack.currentIndex(),4)
        self.assertTrue(self.window.new_project_button.isVisible())
        self.assertFalse(self.window.info_label.isVisible())
        self.assertTrue(self.window.project_tiles[self.project['id']].isVisible())

    def test_dataset_card_opens_library_and_annotation(self):
        self.window.select_project_card(self.project['id']);APP.processEvents()
        QTest.mouseClick(self.window.dataset_card,Qt.MouseButton.LeftButton,pos=QPoint(10,10));APP.processEvents()
        self.assertEqual(self.window.stack.currentIndex(),5)
        page=self.window.dataset_page;self.assertEqual(page.list.count(),1)
        page.list.item(0).setSelected(True);APP.processEvents();self.assertTrue(page.annotate_button.isEnabled())
        page.annotate_button.click();APP.processEvents();self.assertEqual(self.window.stack.currentIndex(),1);self.assertEqual(self.window.current['id'],self.image['id'])
        self.assertFalse(self.window.windowIcon().pixmap(16,16).isNull())

    def test_dataset_preprocessing_and_recoverable_removal(self):
        self.window.select_project_card(self.project['id']);self.window.go(5);APP.processEvents();page=self.window.dataset_page;page.list.item(0).setSelected(True)
        callbacks=[]
        def finish_prepare():
            try:
                dialog=APP.activeModalWidget();dialog.operation.setCurrentIndex(dialog.operation.findData('resize'));dialog.edge.setValue(320);dialog.update_preview();dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
            except Exception as exc:
                callbacks.append(exc)
                if APP.activeModalWidget():APP.activeModalWidget().reject()
        QTimer.singleShot(0,finish_prepare);page.prepare_button.click();APP.processEvents()
        self.assertEqual(callbacks,[]);self.assertEqual(len(self.window.images),2)
        child=next(im for im in self.window.images if im['id']!=self.image['id']);self.assertEqual(child['width'],320);self.assertEqual(child['status'],'draft')
        page.list.clearSelection()
        for i in range(page.list.count()):
            if page.list.item(i).data(Qt.ItemDataRole.UserRole)==child['id']:page.list.item(i).setSelected(True)
        confirm_timer=QTimer()
        def confirm_removal():
            modal=APP.activeModalWidget()
            if isinstance(modal,QMessageBox):modal.button(QMessageBox.StandardButton.Yes).click();confirm_timer.stop()
        confirm_timer.timeout.connect(confirm_removal);confirm_timer.start(10);page.remove_button.click();APP.processEvents();confirm_timer.stop()
        self.assertEqual(len(self.window.images),1);self.assertTrue(self.store.path(child['path']).is_file())
        page.filter.setCurrentIndex(page.filter_keys.index('trash'));APP.processEvents();self.assertEqual(page.list.count(),1);page.list.item(0).setSelected(True);page.restore_button.click();APP.processEvents()
        self.assertEqual(len(self.window.images),2);self.assertEqual(page.list.count(),0)

    def test_sidebar_collapse_and_autolabel_train_first_prompt(self):
        self.window.select_project_card(self.project['id']);APP.processEvents()
        self.assertTrue(self.window.sidebar.isVisible())
        self.window.sidebar_collapse_btn.click();APP.processEvents()
        self.assertFalse(self.window.sidebar.isVisible())
        self.window.sidebar_toggle.click();APP.processEvents()
        self.assertTrue(self.window.sidebar.isVisible())

        self.window.go(2);APP.processEvents()
        self.assertGreaterEqual(self.window.train_name.height(),30)
        self.assertGreaterEqual(self.window.epochs.height(),30)
        self.assertGreaterEqual(self.window.batch.height(),30)

        self.window.go(1);APP.processEvents()
        self.assertFalse(self.window.model_matches_project('model','yolo11n.pt'))
        confirm_timer=QTimer()
        def confirm_train_first():
            modal=APP.activeModalWidget()
            if isinstance(modal,QMessageBox):
                modal.button(QMessageBox.StandardButton.Yes).click()
                confirm_timer.stop()
        confirm_timer.timeout.connect(confirm_train_first);confirm_timer.start(10)
        self.window.prompt_train_first('YOLO11n','model','yolo11n.pt');APP.processEvents();confirm_timer.stop()
        self.assertEqual(self.window.stack.currentIndex(),2)

    def test_edit_and_delete_project(self):
        pid=self.project['id']
        def finish_edit():
            dialog=APP.activeModalWidget()
            inputs=dialog.findChildren(QLineEdit)
            inputs[0].setText('DIP_AOI')
            inputs[1].setText('ST02')
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        QTimer.singleShot(0,finish_edit)
        self.window.project_edit_buttons[pid].click();APP.processEvents()
        self.assertEqual(self.window.project()['name'],'DIP_AOI')
        self.assertEqual(self.window.project()['station'],'ST02')

        confirm_timer=QTimer()
        def confirm_delete():
            modal=APP.activeModalWidget()
            if isinstance(modal,QMessageBox):
                modal.button(QMessageBox.StandardButton.Yes).click()
                confirm_timer.stop()
        confirm_timer.timeout.connect(confirm_delete);confirm_timer.start(10)
        self.window.project_delete_buttons[pid].click();APP.processEvents();confirm_timer.stop()
        self.assertEqual(self.window.projects,[])
        self.assertEqual(self.window.stack.currentIndex(),4)


if __name__=='__main__':unittest.main()
