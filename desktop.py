"""Native Qt widgets for the complete image-to-model workflow."""
from __future__ import annotations

import copy
import json
import os
import shutil
import zipfile
from datetime import datetime
from functools import wraps
from pathlib import Path

from PySide6.QtCore import QEventLoop, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QKeySequence, QPainter, QPen, QPixmap, QPolygonF, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QProgressDialog, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from canvas import AnnotationCanvas, COLORS, thumbnail
from core import AppError, require, uid
from dataset import DatasetPage,TEXT as DATASET_TEXT
from app_icon import application_icon

BASE = Path(__file__).resolve().parent
MESSAGES = json.loads((BASE/'translations.json').read_text(encoding='utf-8'))
MESSAGES.update({
    'manageClasses':['管理標註類別','管理标注类别','Manage annotation classes'],
    'stationOptional':['檢測工站（選填）','检测工站（选填）','Inspection station (optional)'],
    'stationExample':['例如 ST01、DIP 外觀檢測；可留空','例如 ST01、DIP 外观检测；可留空','e.g. ST01, DIP inspection; may be blank'],
    'classesLater':['可留空，進入專案後再到「管理標註類別」新增。','可留空，进入项目后再到“管理标注类别”新增。','Optional. Add classes later using Manage annotation classes.'],
    'classOrderLocked':['既有類別名稱與順序需保留，請在最後新增類別。','请保留已有类别名称与顺序，在末尾新增类别。','Keep existing class names and order; append new classes.'],
    'addClass':['新增類別','新增类别','Add class'],
    'addClassPrompt':['請輸入新類別名稱：','请输入新类别名称：','Enter new class name:'],
    'toggleDeleteMode':['切換刪除類別模式','切换删除类别模式','Toggle delete class mode'],
    'deleteClassConfirm':['確定要刪除類別「{name}」？相關標註框將一併移除。','确定要删除类别“{name}”？相关标注框将一并移除。','Delete class "{name}"? Associated boxes will also be removed.'],
    'resetView':['重設縮放','重置缩放','Reset view'],
    'toggleSidebar':['收合 / 展開側邊目錄 (Ctrl+B)','收起 / 展开侧边目录 (Ctrl+B)','Toggle sidebar (Ctrl+B)'],
    'collapseSidebar':['⟨ 收合目錄','⟨ 收起目录','⟨ Hide sidebar'],
    'classMismatchTitle':['模型類別與專案不相符','模型类别与项目不匹配','Model classes do not match project'],
    'trainFirstPrompt':[
        '所選模型「{model}」的類別與目前專案類別（{classes}）沒有相符名稱，無法直接自動標註。\n\n是否要先訓練一版專案模型來進行標註？',
        '所选模型“{model}”的类别与当前项目类别（{classes}）没有匹配名称，无法直接自动标注。\n\n是否要先训练一版项目模型来进行标注？',
        'Selected model "{model}" has no matching class names for this project ({classes}).\n\nWould you like to train a project model first?'
    ],
    'trainFirstReadyHint':[
        '目前已審核 {reviewed} 張圖片，可直接開始訓練一版模型。',
        '当前已审核 {reviewed} 张图片，可直接开始训练一版模型。',
        '{reviewed} reviewed images are ready to train a first model version.'
    ],
    'trainFirstNeedImagesHint':[
        '目前僅有 {reviewed} 張已審核圖片（訓練至少需要 3 張已審核且含物件框的圖片）。可先前往訓練中心查看設定，或先標註並審核 3 張圖片。',
        '当前仅有 {reviewed} 张已审核图片（训练至少需要 3 张已审核且含目标框的图片）。可先前往训练中心查看设置，或先标注并审核 3 张图片。',
        'Only {reviewed} reviewed images found (at least 3 reviewed images with boxes are required). You can open Training Center or review 3 images first.'
    ],
    'trainNowBtn':['立即訓練一版','立即训练一版','Train a version now'],
    'goTrainCenterBtn':['前往訓練中心','前往训练中心','Open Training Center'],
    'classMismatchShort':[
        '模型類別與專案（{classes}）不相符，請先訓練專案模型後再自動標註。',
        '模型类别与项目（{classes}）不匹配，请先训练项目模型后再自动标注。',
        'Model classes do not match project ({classes}). Train a project model first.'
    ],

    'native': ['Windows 桌面版','Windows 桌面版','WINDOWS DESKTOP'],
    'chooseFolder': ['選擇儲存位置','选择保存位置','Choose save location'],
    'fileSaved': ['檔案已儲存：{path}','文件已保存：{path}','Saved: {path}'],
    'stopOnClose': ['關閉軟體將停止目前任務，確定關閉？','关闭软件将停止当前任务，确定关闭？','Closing the application will stop the active run. Close anyway?'],
    'refresh': ['重新整理','刷新','Refresh'],
    'boxClass': ['選取框的類別','选中框的类别','Selected object class'],
    'delete': ['刪除選取框','删除选中框','Remove selected object'],
    'importFolder': ['匯入資料夾','导入文件夹','Import folder'],
    'saveError': ['無法儲存','无法保存','Could not save'],
    'generalError': ['操作未完成','操作未完成','Action could not be completed'],
    'confirm': ['請確認','请确认','Confirm'],
    'splitCounts': ['訓練 {train} ／ 驗證 {val} ／ 測試 {test}','训练 {train} ／ 验证 {val} ／ 测试 {test}','Train {train} / validation {val} / test {test}'],
    'importCancelled': ['匯入已停止，已匯入的圖片保留','导入已停止，已导入的图片保留','Import stopped. Already imported images are retained.'],
    'importErrors': ['{count} 個檔案匯入失敗：','{count} 个文件导入失败：','{count} files could not be imported:'],
    'modelFileHint': ['請選擇您信任的 Ultralytics .pt 偵測模型','请选择您信任的 Ultralytics .pt 检测模型','Select a trusted Ultralytics .pt detection model'],
    'cancel': ['取消','取消','Cancel'],
    'yes': ['是','是','Yes'],
    'no': ['否','否','No'],
    'ok': ['確定','确定','OK'],
    'status': ['狀態','状态','Status'],
    'taskType': ['任務類型','任务类型','Task type'],
    'progressLabel': ['進度','进度','Progress'],
    'overview': ['專案工作台','项目工作台','Project dashboard'],
    'homeEyebrow': ['專案管理','项目管理','YOUR PROJECTS'],
    'homeTitle': ['專案總覽','项目总览','Projects'],
    'homeDescription': ['建立新的產品專案，或選取一張專案卡開始工作。','创建新的产品项目，或选择一张项目卡开始工作。','Create a product project or select a project card to get started.'],
    'allProjects': ['所有專案','所有项目','All projects'],
    'projectCount': ['共 {count} 個專案','共 {count} 个项目','{count} projects'],
    'newProjectCard': ['＋\n新增專案','＋\n新建项目','＋\nNew project'],
    'selectProject': ['選取此專案','选择此项目','Select project'],
    'openProject': ['開始標註 →','开始标注 →','Start labeling →'],
    'selectedProject': ['目前專案：{name}','当前项目：{name}','Current project: {name}'],
    'projectCardCounts': ['{images} 張圖片  ·  {reviewed} 張已審核  ·  {models} 個模型','{images} 张图片  ·  {reviewed} 张已审核  ·  {models} 个模型','{images} images · {reviewed} reviewed · {models} models'],
    'projectSelected': ['已切換至專案：{name}','已切换至项目：{name}','Switched to project: {name}'],
    'backProjects': ['← 所有專案','← 所有项目','← All projects'],
    'enterProject': ['開啟專案 →','打开项目 →','Open project →'],
    'lastProject': ['上次開啟','上次打开','Last opened'],
    'editProject': ['編輯專案','编辑项目','Edit project'],
    'deleteProject': ['刪除專案','删除项目','Delete project'],
    'deleteProjectConfirm': [
        '確定要刪除專案「{name}」嗎？\n此專案內的所有圖片、標註與模型將一併移除且無法復原。',
        '确定要删除项目“{name}”吗？\n此项目内的所有图片、标注与模型将一并移除且无法恢复。',
        'Delete project "{name}"?\nAll images, annotations, and models in this project will be permanently removed.'
    ],
    'projectUpdated': ['已更新專案：{name}','已更新项目：{name}','Updated project: {name}'],
    'projectDeleted': ['已刪除專案：{name}','已删除项目：{name}','Deleted project: {name}'],
    'save': ['儲存','保存','Save'],
    'gpu_fallback_cpu': ['GPU 初始化失敗，改用 CPU','GPU 初始化失败，改用 CPU','GPU initialization failed; using CPU'],
})
MESSAGES.update(DATASET_TEXT)
MESSAGES['engineSetup'] = ['人工標註已可使用。自動標註與訓練需先安裝 YOLO 引擎，完成後重新啟動。','人工标注已可使用。自动标注与训练需先安装 YOLO 引擎，完成后重新启动。','Manual labeling is available. Install the YOLO engine and restart to enable auto-labeling and training.']

COCO_CLASSES = {
    'person','bicycle','car','motorcycle','airplane','bus','train','truck','boat','traffic light',
    'fire hydrant','stop sign','parking meter','bench','bird','cat','dog','horse','sheep','cow',
    'elephant','bear','zebra','giraffe','backpack','umbrella','handbag','tie','suitcase','frisbee',
    'skis','snowboard','sports ball','kite','baseball bat','baseball glove','skateboard','surfboard',
    'tennis racket','bottle','wine glass','cup','fork','knife','spoon','bowl','banana','apple',
    'sandwich','orange','broccoli','carrot','hot dog','pizza','donut','cake','chair','couch',
    'potted plant','bed','dining table','toilet','tv','laptop','mouse','remote','keyboard',
    'cell phone','microwave','oven','toaster','sink','refrigerator','book','clock','vase',
    'scissors','teddy bear','hair drier','toothbrush'
}

def _ensure_spin_icons():
    assets = BASE / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    up_path = (assets / 'spin-up.png').as_posix()
    down_path = (assets / 'spin-down.png').as_posix()
    if not (assets / 'spin-up.png').is_file() or not (assets / 'spin-down.png').is_file():
        from PIL import Image, ImageDraw
        for name, pts in [('spin-up.png', [(2, 7), (6, 3), (10, 7)]), ('spin-down.png', [(2, 3), (6, 7), (10, 3)])]:
            img = Image.new('RGBA', (12, 10), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.line(pts, fill=(65, 88, 106, 255), width=2)
            img.save(assets / name)
    return up_path, down_path

_SPIN_UP, _SPIN_DOWN = _ensure_spin_icons()

STYLE = '''
QWidget {font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI", "Microsoft JhengHei", "Microsoft YaHei";font-size:13px;color:#1d2d3e;}
QMainWindow, QWidget#content {background:#f5f7fa;}
QWidget#homeBody {background:#f5f7fa;}
QFrame#sidebar {background:#142e33;} QFrame#sidebar QLabel {color:#94b1b5;background:transparent;}
QFrame#sidebar QLabel#brand {color:#f5fffc;font-size:22px;font-weight:600;}
QFrame#sidebar QPushButton {text-align:left;color:#a8c3c5;background:transparent;border:0;padding:11px 14px;border-radius:8px;font-size:13px;}
QFrame#sidebar QPushButton:hover {background:rgba(255,255,255,0.06);color:#e2f4f0;}
QFrame#sidebar QPushButton:checked {background:#24504f;color:#83e3ca;font-weight:600;}
QFrame#sidebar QPushButton#newProject {border:1px solid #426166;padding:10px;}
QFrame#sidebar QPushButton#sidebarCollapseBtn {text-align:center;padding:0px;min-width:28px;max-width:28px;min-height:28px;max-height:28px;font-size:15px;font-weight:700;color:#a8c9cc;background:rgba(255,255,255,0.07);border:1px solid #2f5258;border-radius:7px;}
QFrame#sidebar QPushButton#sidebarCollapseBtn:hover {background:#24504f;color:#ffffff;border-color:#538d8a;}
QFrame#sidebar QComboBox {background:#203f44;color:#e0eeeb;border:1px solid #36565b;min-height:22px;padding:5px 10px;}
QFrame#sidebar QLabel#sidebarCaption {color:#789b9f;font-size:11px;font-weight:500;}
QFrame#topbar {background:white;border-bottom:1px solid #e4eaf0;}
QFrame#card {background:white;border:1px solid #e1e8ed;border-radius:12px;}
QFrame#projectCard {background:white;border:1px solid #dce5e9;border-radius:12px;}
QFrame#projectCard:hover {border:1px solid #65b4a2;background:#fcfffd;}
QFrame#projectCard[active="true"] {background:#f1fbf6;border:2px solid #15957e;}
QFrame#projectCard:focus {border:2px solid #15957e;}
QLabel#projectBadge {color:#087f75;background:#dff2e9;border-radius:5px;padding:5px 8px;font-size:10px;}
QPushButton#newProjectTile {background:#f5fbf8;color:#368675;border:1px dashed #a8cabe;border-radius:12px;font-size:17px;min-height:220px;}
QPushButton#newProjectTile:hover {background:#e8f7ef;border-color:#14957e;}
QLabel#eyebrow {color:#0b8b7b;font-size:11px;font-weight:600;letter-spacing:1.5px;}
QLabel#title {font-size:25px;font-weight:600;color:#1d2f43;}
QLabel#subtitle {font-size:12px;color:#6c7f90;}
QLabel#section {font-size:15px;font-weight:600;color:#24384b;}
QLabel#statNumber {font-size:32px;font-weight:600;color:#1c3b42;}
QLabel#statLabel {color:#7d8d9c;font-size:12px;}
QLabel#notice {background:#fff8eb;border:1px solid #edd9b4;border-radius:8px;color:#8a6829;padding:8px 12px;}
QLabel#success {background:#eaf6ef;border:1px solid #cce8d8;border-radius:8px;color:#2f7d63;padding:8px 12px;font-weight:500;}
QPushButton {background:white;border:1px solid #d6e0e6;border-radius:8px;padding:7px 14px;color:#3f5364;font-weight:500;min-height:20px;}
QPushButton:hover {background:#f0f7f4;border-color:#9ec8b9;}
QPushButton:pressed {background:#dfeee8;}
QPushButton:disabled {color:#b0bac2;background:#f2f5f7;border-color:#e4eaee;}
QPushButton#primary {background:#087f75;border:1px solid #087f75;color:white;font-weight:600;}
QPushButton#primary:hover {background:#096d65;}
QPushButton#primary:disabled {background:#a5c7be;border-color:#a5c7be;color:#eef6f4;}
QPushButton#iconBtn {padding:0px;min-width:28px;max-width:28px;min-height:28px;max-height:28px;font-size:16px;font-weight:700;color:#087f75;background:#f2fbf7;border:1px solid #bce0d3;border-radius:7px;}
QPushButton#iconBtn:hover {background:#dff5ec;border-color:#087f75;}
QPushButton#dangerIconBtn {padding:0px;min-width:28px;max-width:28px;min-height:28px;max-height:28px;font-size:15px;font-weight:700;color:#c0392b;background:#fff6f6;border:1px solid #f1c8c8;border-radius:7px;}
QPushButton#dangerIconBtn:hover, QPushButton#dangerIconBtn:checked {background:#ffe5e5;border-color:#c0392b;color:#9e1f14;}
QPushButton#sidebarToggle {padding:0px;min-width:34px;max-width:34px;min-height:34px;max-height:34px;font-size:16px;color:#355064;background:#f6f9fb;border:1px solid #dce5ec;border-radius:8px;}
QPushButton#sidebarToggle:hover {background:#eaf4f0;border-color:#8ec8b7;color:#087f75;}
QPushButton#drop {background:#f6fcf9;border:1px dashed #9fc7bb;border-radius:10px;padding:36px 20px;color:#468b7a;font-size:15px;}
QPushButton#tool:checked {background:#e4f5ec;color:#087f75;border-color:#9ad0bc;font-weight:600;}
QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox {background:white;border:1px solid #d5dfe6;border-radius:8px;padding:4px 10px;min-height:22px;font-size:13px;color:#1d2d3e;selection-background-color:#c9e9de;}
QSpinBox,QDoubleSpinBox {padding-right:26px;}
QSpinBox::up-button,QDoubleSpinBox::up-button {subcontrol-origin:border;subcontrol-position:top right;width:22px;border-left:1px solid #e1e9ee;border-bottom:1px solid #e1e9ee;border-top-right-radius:7px;background:#f8fafb;}
QSpinBox::down-button,QDoubleSpinBox::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:22px;border-left:1px solid #e1e9ee;border-bottom-right-radius:7px;background:#f8fafb;}
QSpinBox::up-button:hover,QSpinBox::down-button:hover,QDoubleSpinBox::up-button:hover,QDoubleSpinBox::down-button:hover {background:#e6f4ee;}
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow {image:url("''' + _SPIN_UP + '''");width:10px;height:8px;}
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow {image:url("''' + _SPIN_DOWN + '''");width:10px;height:8px;}
QPlainTextEdit,QTextEdit {background:white;border:1px solid #d5dfe6;border-radius:8px;padding:8px;selection-background-color:#c9e9de;}
QComboBox QAbstractItemView {background:white;color:#243549;selection-background-color:#d9eee6;outline:0;}
QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus {border:1px solid #15957e;}
QListWidget {background:white;border:1px solid #e1e8ed;border-radius:8px;outline:0;}
QListWidget::item {padding:8px 6px;border-bottom:1px solid #f2f5f7;}
QListWidget#classList::item {padding:2px 4px;border-bottom:1px solid #f2f5f7;}
QListWidget::item:selected {background:#e0f3ea;color:#186959;border-left:3px solid #149a7f;}
QTableWidget {background:white;border:1px solid #e0e7ec;border-radius:8px;gridline-color:#eef2f4;selection-background-color:#e4f3ed;selection-color:#2a6156;outline:0;}
QHeaderView::section {background:#f5f8fa;color:#667a8a;border:0;border-bottom:1px solid #e2e9ee;padding:9px 12px;font-weight:600;}
QTableWidget::item {padding:8px 10px;}
QProgressBar {min-height:10px;max-height:10px;border:0;background:#e5eeeb;border-radius:5px;text-align:center;font-size:10px;color:#24473e;}
QProgressBar::chunk {background:#12957e;border-radius:5px;}
QPlainTextEdit#logs {background:#172e34;color:#b5d6d0;font-family:Consolas,"Cascadia Mono",monospace;font-size:12px;border-radius:8px;border:0;padding:10px;}
QScrollArea {border:0;background:transparent;}QSplitter::handle {background:#e4eaee;width:2px;}
QStatusBar {background:white;border-top:1px solid #e5ebef;color:#698276;}
QDialog {background:#f8fafb;}QToolTip {color:#24473e;background:#e9f5ef;border:1px solid #b2d3c5;padding:5px;}
'''


def ui_icon(kind, color='#355064', size=18):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    if kind == 'sidebar':
        p.drawRoundedRect(2, 3, size - 4, size - 6, 2.5, 2.5)
        p.drawLine(7, 3, 7, size - 3)
        p.drawLine(4, 6, 5, 6)
        p.drawLine(4, 9, 5, 9)
    elif kind == 'trash':
        p.drawLine(3, 5, size - 3, 5)
        p.drawLine(7, 3, size - 7, 3)
        p.drawRoundedRect(5, 5, size - 10, size - 8, 1.5, 1.5)
        p.drawLine(8, 8, 8, size - 6)
        p.drawLine(10, 8, 10, size - 6)
    elif kind == 'plus':
        m = size // 2
        p.drawLine(m, 4, m, size - 4)
        p.drawLine(4, m, size - 4, m)
    elif kind == 'minus':
        m = size // 2
        p.drawLine(4, m, size - 4, m)
    elif kind == 'edit':
        s = size / 18.0
        poly = QPolygonF([
            QPointF(11.8 * s, 2.8 * s),
            QPointF(15.2 * s, 6.2 * s),
            QPointF(6.5 * s, 14.9 * s),
            QPointF(3.0 * s, 15.0 * s),
            QPointF(3.1 * s, 11.5 * s),
        ])
        p.drawPolygon(poly)
        p.drawLine(QPointF(9.6 * s, 5.0 * s), QPointF(13.0 * s, 8.4 * s))
    p.end()
    return QIcon(pm)


def guarded(function):
    @wraps(function)
    def call(self,*args,**kwargs):
        try:return function(self,*args,**kwargs)
        except Exception as exc:self.error(exc)
    return call


class ProjectTile(QFrame):
    activated = Signal(str)

    def __init__(self,identity):
        super().__init__()
        self.identity=identity
        self.setObjectName('projectCard')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(238)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit(self.identity)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Space):
            self.activated.emit(self.identity);event.accept()
        else:super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self,store,manager):
        super().__init__()
        # Qt's offscreen Windows plugin has no system font database by default.
        # Explicit fonts keep native preview/test renders faithful to the desktop.
        if not QFontDatabase.families():
            fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('segoeui.ttf','msjh.ttc','msjhbd.ttc','msyh.ttc'):
                if (fonts/name).is_file():QFontDatabase.addApplicationFont(str(fonts/name))
        self.store,self.manager=store,manager
        self.pref_path=store.path('preferences.json')
        try:self.prefs=json.loads(self.pref_path.read_text(encoding='utf-8'))
        except (FileNotFoundError,ValueError):self.prefs={}
        self.lang=self.prefs.get('language','zh-TW')
        if self.lang not in ('zh-TW','zh-CN','en'):self.lang='zh-TW'
        self.bindings=[]
        self.project_id=self.prefs.get('project','')
        self.projects,self.images,self.models,self.jobs=[],[],[],[]
        self.current=None;self.dirty=False;self.log_job='';self.image_signature=None;self.model_signature=None;self.thumbnails={};self.importing=False;self.last_default='';self.project_card_signature=None
        self.setWindowTitle('YOLO Studio — '+self.tr('native'))
        self.setWindowIcon(application_icon())
        self.resize(1440,920);self.setMinimumSize(1180,760)
        self.setStyleSheet(STYLE)
        self.autosave=QTimer(self);self.autosave.setSingleShot(True);self.autosave.setInterval(900);self.autosave.timeout.connect(self.save_draft)
        self.build()
        self.refresh()
        self.timer=QTimer(self);self.timer.setInterval(1800);self.timer.timeout.connect(self.refresh);self.timer.start()
        self.statusBar().showMessage(self.tr('localHint'))
        self.shortcuts()

    def tr(self,key,**values):
        text=MESSAGES.get(key,[key,key,key])[('zh-TW','zh-CN','en').index(self.lang)]
        for k,v in values.items():text=text.replace('{'+k+'}',str(v))
        return text

    def bind(self,widget,key,setter='setText'):
        self.bindings.append((widget,key,setter));text=self.tr(key)
        if isinstance(widget,QPushButton):text=text.replace('&','&&')
        getattr(widget,setter)(text);return widget

    def label(self,key,style=None,wrap=False):
        widget=QLabel();widget.setTextFormat(Qt.TextFormat.PlainText);widget.setWordWrap(wrap)
        if style:widget.setObjectName(style)
        return self.bind(widget,key)

    def button(self,key,callback=None,primary=False):
        widget=self.bind(QPushButton(),key)
        if primary:widget.setObjectName('primary')
        if callback:widget.clicked.connect(callback)
        return widget

    def card(self):
        frame=QFrame();frame.setObjectName('card');layout=QVBoxLayout(frame);layout.setContentsMargins(22,22,22,22);layout.setSpacing(16)
        return frame,layout

    def heading(self,page,eyebrow,title,description,button=None):
        row=QHBoxLayout();col=QVBoxLayout();col.setSpacing(5)
        col.addWidget(self.label(eyebrow,'eyebrow'));col.addWidget(self.label(title,'title'));col.addWidget(self.label(description,'subtitle',True));row.addLayout(col,1)
        if button:row.addWidget(button)
        page.addLayout(row)

    def make_page(self):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(26,16,26,14);layout.setSpacing(14)
        self.stack.addWidget(page);return page,layout

    def build(self):
        root=QWidget();outer=QHBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0);self.setCentralWidget(root)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(220);self.sidebar=side;sl=QVBoxLayout(side);sl.setContentsMargins(18,24,18,22);sl.setSpacing(8)
        brand_row=QHBoxLayout();brand_row.setSpacing(9);brand_icon=QLabel();brand_icon.setPixmap(QPixmap(str(BASE/'assets/app-icon.png')).scaled(30,30,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));brand_row.addWidget(brand_icon)
        brand=QLabel('YOLO Studio');brand.setObjectName('brand');brand.setStyleSheet('font-size:20px;');brand_row.addWidget(brand);brand_row.addStretch()
        self.sidebar_collapse_btn=QPushButton('«');self.sidebar_collapse_btn.setObjectName('sidebarCollapseBtn');self.sidebar_collapse_btn.setFixedSize(28,28);self.sidebar_collapse_btn.setToolTip(self.tr('toggleSidebar'));self.sidebar_collapse_btn.clicked.connect(self.toggle_sidebar);brand_row.addWidget(self.sidebar_collapse_btn)
        sl.addLayout(brand_row);sl.addWidget(self.label('brandSub','sidebarCaption'));sl.addSpacing(14)
        self.project_context_label=self.label('currentProject','sidebarCaption');sl.addWidget(self.project_context_label);self.project_select=QComboBox();self.project_select.setAccessibleName(self.tr('currentProject'));self.project_select.currentIndexChanged.connect(self.change_project);sl.addWidget(self.project_select)
        self.new_project_button=self.button('newProject',self.new_project);self.new_project_button.setObjectName('newProject');sl.addWidget(self.new_project_button);sl.addSpacing(10)
        self.home_button=self.button('backProjects',lambda:self.go(4));self.home_button.setCheckable(True);sl.addWidget(self.home_button)
        self.workflow_label=self.label('workflow','sidebarCaption');sl.addWidget(self.workflow_label)
        self.nav=[]
        self.dataset_nav=self.button('datasetTitle',lambda:self.go(5));self.dataset_nav.setCheckable(True)
        for i,key in enumerate(('overview','annotate','train','models')):
            button=self.button(key,lambda checked=False,n=i:self.go(n));button.setCheckable(True);self.nav.append(button);sl.addWidget(button)
            if i==0:sl.addWidget(self.dataset_nav)
        sl.addStretch();self.engine_label=QLabel();self.engine_label.setWordWrap(True);sl.addWidget(self.engine_label);sl.addWidget(self.label('localHint','sidebarCaption',True));sl.addSpacing(6)
        self.language=QComboBox();self.language.addItems(['繁體中文','简体中文','English']);self.language.setCurrentIndex(('zh-TW','zh-CN','en').index(self.lang));self.language.currentIndexChanged.connect(self.change_language);self.language.setAccessibleName('Language');sl.addWidget(self.language);outer.addWidget(side)
        content=QWidget();content.setObjectName('content');cl=QVBoxLayout(content);cl.setContentsMargins(0,0,0,0);cl.setSpacing(0)
        bar=QFrame();bar.setObjectName('topbar');bar.setFixedHeight(52);bl=QHBoxLayout(bar);bl.setContentsMargins(20,0,28,0);bl.setSpacing(10)
        self.sidebar_toggle=QPushButton();self.sidebar_toggle.setIcon(ui_icon('sidebar','#355064',18));self.sidebar_toggle.setIconSize(QSize(18,18));self.sidebar_toggle.setObjectName('sidebarToggle');self.sidebar_toggle.setFixedSize(34,34);self.sidebar_toggle.setToolTip(self.tr('toggleSidebar'));self.sidebar_toggle.clicked.connect(self.toggle_sidebar);bl.addWidget(self.sidebar_toggle)
        bl.addWidget(self.label('workspace','subtitle'));bl.addWidget(QLabel('/'));self.project_title=QLabel();bl.addWidget(self.project_title);bl.addStretch();bl.addWidget(self.label('native','eyebrow'));cl.addWidget(bar)
        self.stack=QStackedWidget();cl.addWidget(self.stack);outer.addWidget(content,1)
        self.build_overview();self.build_annotation();self.build_training();self.build_models();self.build_home();self.dataset_page=DatasetPage(self);self.stack.addWidget(self.dataset_page)
        if self.prefs.get('sidebar_collapsed'):self.sidebar.setVisible(False)
        self.go(4)

    def toggle_sidebar(self):
        visible = not self.sidebar.isVisible()
        self.sidebar.setVisible(visible)
        self.prefs['sidebar_collapsed'] = not visible
        self.persist()

    def build_overview(self):
        _,layout=self.make_page();self.heading(layout,'overviewEyebrow','overviewTitle','overviewDesc',self.button('importImages',self.import_dialog,True))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
        body=QWidget();body.setObjectName('homeBody');content=QVBoxLayout(body);content.setContentsMargins(0,0,8,0);content.setSpacing(22);content.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        stats=QHBoxLayout();stats.setSpacing(15);self.stat_labels=[]
        for key in ('totalImages','reviewedCount','pendingCount','modelCount'):
            frame,col=self.card();col.addWidget(self.label(key,'statLabel'));number=QLabel('0');number.setObjectName('statNumber');col.addWidget(number);self.stat_labels.append(number);stats.addWidget(frame)
        content.addLayout(stats);content.addWidget(self.label('pipelineTitle','section'));flow=QHBoxLayout();flow.setSpacing(12)
        for i,key in enumerate(('stepImport','stepLabel','stepTrain','stepExport')):
            frame,col=self.card();col.setSpacing(8);col.addWidget(self.label(key,'section'));col.addWidget(self.label(key+'Desc','subtitle',True));button=QPushButton(f'0{i+1}  →');button.clicked.connect(lambda checked=False,n=i:self.go((1,1,2,3)[n]));col.addWidget(button);flow.addWidget(frame)
        content.addLayout(flow);bottom=QHBoxLayout();bottom.setSpacing(20)
        self.dataset_card=ProjectTile('dataset');self.dataset_card.activated.connect(lambda identity:self.go(5));col=QVBoxLayout(self.dataset_card);col.setContentsMargins(22,22,22,22);col.setSpacing(14);col.addWidget(self.label('dataset','eyebrow'));col.addWidget(self.label('datasetTitle','section'));col.addWidget(self.label('datasetCardHint','subtitle',True));self.dataset_card_count=QLabel();self.dataset_card_count.setObjectName('section');col.addWidget(self.dataset_card_count);col.addWidget(self.button('manageDataset',lambda:self.go(5),True));buttons=QHBoxLayout();buttons.addWidget(self.button('importImages',self.import_dialog));buttons.addWidget(self.button('importFolder',self.import_folder));col.addLayout(buttons);bottom.addWidget(self.dataset_card,3)
        frame,col=self.card();col.addWidget(self.label('projectInfo','section'));self.info_label=QLabel();self.info_label.setTextFormat(Qt.TextFormat.PlainText);self.info_label.setWordWrap(True);self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop);col.addWidget(self.info_label,1);col.addWidget(self.button('manageClasses',self.manage_classes))
        proj_act=QHBoxLayout();proj_act.setSpacing(8);self.edit_project_btn=self.button('editProject',lambda:self.edit_project(self.project_id));self.delete_project_btn=self.button('deleteProject',lambda:self.delete_project(self.project_id));proj_act.addWidget(self.edit_project_btn,1);proj_act.addWidget(self.delete_project_btn,1);col.addLayout(proj_act)
        self.engine_notice=self.label('engineSetup','notice',True);col.addWidget(self.engine_notice);bottom.addWidget(frame,2);content.addLayout(bottom);content.addStretch();scroll.setWidget(body);layout.addWidget(scroll,1)
        self.setAcceptDrops(True)

    def build_home(self):
        _,layout=self.make_page();self.heading(layout,'homeEyebrow','homeTitle','homeDescription',self.button('newProject',self.new_project,True))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
        body=QWidget();body.setObjectName('homeBody');content=QVBoxLayout(body);content.setContentsMargins(0,0,8,0);content.setSpacing(20);content.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        section=QHBoxLayout();section.addWidget(self.label('allProjects','section'));section.addStretch();self.project_count=QLabel();self.project_count.setObjectName('subtitle');section.addWidget(self.project_count);content.addLayout(section)
        self.project_grid_host=QWidget();self.project_grid=QGridLayout(self.project_grid_host);self.project_grid.setContentsMargins(0,0,0,0);self.project_grid.setSpacing(16)
        for column in range(3):self.project_grid.setColumnStretch(column,1)
        content.addWidget(self.project_grid_host);self.project_tiles={};self.project_card_buttons={}
        content.addStretch();scroll.setWidget(body);layout.addWidget(scroll,1)

    def render_project_cards(self,summaries):
        signature=(self.lang,self.project_id,tuple((p['id'],p['name'],p['station'],p['image_count'],p['reviewed_count'],p['model_count']) for p in summaries))
        if signature==self.project_card_signature:return
        self.project_card_signature=signature
        rows=(len(summaries)+3)//3
        self.project_grid_host.setMinimumHeight(rows*238+(rows-1)*16)
        while self.project_grid.count():
            item=self.project_grid.takeAt(0)
            if item.widget():item.widget().hide();item.widget().deleteLater()
        self.project_tiles={};self.project_card_buttons={};self.project_edit_buttons={};self.project_delete_buttons={}
        self.project_count.setText(self.tr('projectCount',count=len(summaries)))
        add=QPushButton(self.tr('newProjectCard'));add.setObjectName('newProjectTile');add.setMinimumHeight(238);add.clicked.connect(self.new_project);self.new_project_tile=add;self.project_grid.addWidget(add,0,0)
        for i,p in enumerate(summaries,1):
            tile=ProjectTile(p['id']);tile.setProperty('active',p['id']==self.project_id);tile.setAccessibleName(p['name']);tile.activated.connect(self.select_project_card)
            col=QVBoxLayout(tile);col.setContentsMargins(20,18,20,18);col.setSpacing(12)
            def label(text,style=None):
                widget=QLabel(text);widget.setTextFormat(Qt.TextFormat.PlainText);widget.setWordWrap(True);widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                if style:widget.setObjectName(style)
                return widget
            top=QHBoxLayout();top.setSpacing(6);top.addWidget(label(p['station'],'eyebrow'));top.addStretch()
            if p['id']==self.project_id:
                badge=label('● '+self.tr('lastProject'),'projectBadge');badge.setWordWrap(False);top.addWidget(badge)
            edit_btn=QPushButton();edit_btn.setIcon(ui_icon('edit','#087f75',15));edit_btn.setIconSize(QSize(15,15));edit_btn.setObjectName('iconBtn');edit_btn.setFixedSize(28,28);edit_btn.setToolTip(self.tr('editProject'))
            edit_btn.clicked.connect(lambda checked=False,identity=p['id']:self.edit_project(identity));top.addWidget(edit_btn)
            del_btn=QPushButton();del_btn.setIcon(ui_icon('trash','#c0392b',15));del_btn.setIconSize(QSize(15,15));del_btn.setObjectName('dangerIconBtn');del_btn.setFixedSize(28,28);del_btn.setToolTip(self.tr('deleteProject'))
            del_btn.clicked.connect(lambda checked=False,identity=p['id']:self.delete_project(identity));top.addWidget(del_btn)
            col.addLayout(top);col.addWidget(label(p['name'],'section'));col.addWidget(label(self.tr('created')+'  '+self.date(p['created']),'subtitle'));col.addWidget(label(self.tr('projectCardCounts',images=p['image_count'],reviewed=p['reviewed_count'],models=p['model_count']),'subtitle'));col.addStretch()
            button=QPushButton(self.tr('enterProject'))
            if p['id']==self.project_id:button.setObjectName('primary')
            button.clicked.connect(lambda checked=False,identity=p['id']:self.select_project_card(identity));col.addWidget(button)
            self.project_grid.addWidget(tile,i//3,i%3);self.project_tiles[p['id']]=tile;self.project_card_buttons[p['id']]=button;self.project_edit_buttons[p['id']]=edit_btn;self.project_delete_buttons[p['id']]=del_btn

    @guarded
    def select_project_card(self,identity):
        require(identity in [p['id'] for p in self.projects],'not_found')
        self.set_project(identity)
        self.notify('projectSelected',name=self.project()['name'])
        self.go(0)

    def build_annotation(self):
        _,layout=self.make_page();self.heading(layout,'annotateEyebrow','annotateTitle','annotateDesc',self.button('autoLabel',self.auto_dialog,True))
        splitter=QSplitter();splitter.setChildrenCollapsible(False);layout.addWidget(splitter,1)
        left=QWidget();ll=QVBoxLayout(left);ll.setContentsMargins(0,0,10,0);ll.setSpacing(8);ll.addWidget(self.label('imageList','section'));self.search=QLineEdit();self.bind(self.search,'searchImages','setPlaceholderText');self.search.textChanged.connect(self.render_images);ll.addWidget(self.search)
        self.image_filter=QComboBox();self.filter_keys=('allImages','unlabeled','draft','pending','reviewed','empty','excluded');self.image_filter.addItems([self.tr(k) for k in self.filter_keys]);self.image_filter.currentIndexChanged.connect(self.render_images);ll.addWidget(self.image_filter)
        self.image_list=QListWidget();self.image_list.setIconSize(QSize(45,38));self.image_list.currentItemChanged.connect(self.choose_image);ll.addWidget(self.image_list,1)
        imp_row=QHBoxLayout();imp_row.setSpacing(6);imp_row.addWidget(self.button('importImages',self.import_dialog));imp_row.addWidget(self.button('importFolder',self.import_folder));ll.addLayout(imp_row);splitter.addWidget(left)
        center=QWidget();cc=QVBoxLayout(center);cc.setContentsMargins(0,0,0,0);cc.setSpacing(8);tools=QHBoxLayout();tools.setSpacing(8);self.draw_button=self.button('drawTool',lambda:self.set_mode('draw'));self.select_button=self.button('selectTool',lambda:self.set_mode('select'))
        for button in (self.draw_button,self.select_button):button.setCheckable(True);button.setObjectName('tool');tools.addWidget(button)
        tools.addStretch()
        self.reset_zoom_button=self.button('resetView',lambda:self.canvas.reset_view())
        tools.addWidget(self.reset_zoom_button)
        tools.addWidget(self.button('undo',lambda:self.canvas.undo()));cc.addLayout(tools)
        self.canvas=AnnotationCanvas();self.canvas.empty_text=self.tr('canvasEmpty');self.canvas.setAccessibleName(self.tr('annotateTitle'));self.canvas.edited.connect(self.annotation_edited);self.canvas.selection_changed.connect(self.selection_changed);self.canvas.files_dropped.connect(self.import_paths);self.canvas.need_classes.connect(self.manage_classes);cc.addWidget(self.canvas,1)
        foot=QHBoxLayout();foot.setSpacing(8);prev=QPushButton('←');prev.clicked.connect(lambda:self.navigate(-1));foot.addWidget(prev);self.image_info=QLabel();self.image_info.setObjectName('subtitle');foot.addWidget(self.image_info,1);next_button=QPushButton('→');next_button.clicked.connect(lambda:self.navigate(1));foot.addWidget(next_button);cc.addLayout(foot);splitter.addWidget(center)
        right=QWidget();rr=QVBoxLayout(right);rr.setContentsMargins(10,0,0,0);rr.setSpacing(8)
        class_hdr=QHBoxLayout();class_hdr.setContentsMargins(0,0,0,0);class_hdr.setSpacing(6)
        class_hdr.addWidget(self.label('classes','section'))
        class_hdr.addStretch()
        self.add_class_btn=QPushButton('+');self.add_class_btn.setObjectName('iconBtn');self.add_class_btn.setFixedSize(28,28);self.add_class_btn.setToolTip(self.tr('addClass'))
        self.add_class_btn.clicked.connect(self.prompt_add_class)
        self.del_mode_btn=QPushButton('−');self.del_mode_btn.setObjectName('dangerIconBtn');self.del_mode_btn.setFixedSize(28,28);self.del_mode_btn.setCheckable(True)
        self.del_mode_btn.setToolTip(self.tr('toggleDeleteMode'))
        self.del_mode_btn.toggled.connect(self.toggle_class_delete_mode)
        class_hdr.addWidget(self.add_class_btn);class_hdr.addWidget(self.del_mode_btn)
        rr.addLayout(class_hdr)
        self.class_list=QListWidget();self.class_list.setObjectName('classList');self.class_list.setMinimumHeight(88);self.class_list.setMaximumHeight(150);self.class_list.currentRowChanged.connect(self.set_class);rr.addWidget(self.class_list)
        rr.addWidget(self.label('boxes','section'));self.box_list=QListWidget();self.box_list.setMinimumHeight(88);self.box_list.currentRowChanged.connect(self.select_box);rr.addWidget(self.box_list,1)
        rr.addWidget(self.label('boxClass','subtitle'))
        box_act=QHBoxLayout();box_act.setContentsMargins(0,0,0,0);box_act.setSpacing(6)
        self.box_class=QComboBox();self.box_class.currentIndexChanged.connect(self.change_box_class)
        box_act.addWidget(self.box_class,1)
        self.delete_box_icon_btn=QPushButton();self.delete_box_icon_btn.setIcon(ui_icon('trash','#c0392b',18));self.delete_box_icon_btn.setIconSize(QSize(18,18));self.delete_box_icon_btn.setObjectName('dangerIconBtn');self.delete_box_icon_btn.setFixedSize(36,36)
        self.delete_box_icon_btn.setStyleSheet("min-width:36px;max-width:36px;min-height:36px;max-height:36px;padding:0px;")
        self.delete_box_icon_btn.setToolTip(self.tr('delete'))
        self.delete_box_icon_btn.clicked.connect(lambda:self.canvas.delete_selected())
        box_act.addWidget(self.delete_box_icon_btn)
        rr.addLayout(box_act)
        self.delete_button=self.delete_box_icon_btn
        self.proposal_info=QLabel();self.proposal_info.setWordWrap(True);self.proposal_info.setObjectName('notice');rr.addWidget(self.proposal_info);self.accept_button=self.button('acceptProposals',self.accept_proposals);rr.addWidget(self.accept_button)
        self.review_button=self.button('reviewSave',self.review,True);rr.addWidget(self.review_button)
        sec_row=QHBoxLayout();sec_row.setContentsMargins(0,0,0,0);sec_row.setSpacing(6)
        self.draft_button=self.button('saveDraft',self.save_draft);self.exclude_button=self.button('excludeImage',self.exclude)
        sec_row.addWidget(self.draft_button,1);sec_row.addWidget(self.exclude_button,1);rr.addLayout(sec_row)
        self.save_label=QLabel();self.save_label.setObjectName('subtitle');rr.addWidget(self.save_label);rr.addWidget(self.label('shortcuts','subtitle',True));splitter.addWidget(right)
        splitter.setSizes([210,730,250]);splitter.setStretchFactor(1,1);self.set_mode('draw')

    def build_training(self):
        _,layout=self.make_page();self.heading(layout,'trainEyebrow','trainTitle','trainDesc',self.button('exportDataset',self.export_dataset))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
        body=QWidget();body.setObjectName('homeBody');content=QVBoxLayout(body);content.setContentsMargins(0,0,6,0);content.setSpacing(12)
        row=QHBoxLayout();row.setSpacing(18);frame,col=self.card();col.setContentsMargins(18,14,18,14);col.setSpacing(8);col.addWidget(self.label('trainingConfig','section'))
        form=QFormLayout();form.setVerticalSpacing(8);form.setHorizontalSpacing(14)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        self.train_name=QLineEdit();self.train_name.setMaxLength(100)
        self.train_model=QComboBox()
        self.epochs=QSpinBox();self.epochs.setRange(1,10000);self.epochs.setValue(50)
        self.imgsz=QComboBox();self.imgsz.addItems(['640','320','960','1280'])
        self.batch=QSpinBox();self.batch.setRange(1,128);self.batch.setValue(8)
        self.device=QComboBox();self.device.addItem(self.tr('deviceAuto'),'auto');self.device.addItem('CPU','cpu');self.device.addItem('GPU 0 (CUDA)','0')
        for w in (self.train_name,self.train_model,self.epochs,self.imgsz,self.batch,self.device):
            w.setMinimumHeight(31);w.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        form.addRow(self.label('modelName'),self.train_name)
        form.addRow(self.label('baseModel'),self.train_model)
        form.addRow(self.label('epochs'),self.epochs)
        form.addRow(self.label('imageSize'),self.imgsz)
        form.addRow(self.label('batchSize'),self.batch)
        form.addRow(self.label('device'),self.device)
        col.addLayout(form)
        self.readiness=QLabel();self.readiness.setObjectName('success');self.readiness.setWordWrap(True);col.addWidget(self.readiness);col.addWidget(self.label('splitHint','subtitle',True));self.train_button=self.button('startTraining',self.start_training,True);self.train_button.setMinimumHeight(36);col.addWidget(self.train_button);col.addStretch();row.addWidget(frame,1)
        frame,col=self.card();col.setContentsMargins(18,14,18,14);col.setSpacing(8);col.addWidget(self.label('jobMonitor','section'));self.monitor_title=QLabel();self.monitor_title.setObjectName('section');self.monitor_title.setWordWrap(True);col.addWidget(self.monitor_title);self.progress=QProgressBar();self.progress.setRange(0,100);col.addWidget(self.progress);self.monitor_message=QLabel();self.monitor_message.setTextFormat(Qt.TextFormat.PlainText);self.monitor_message.setWordWrap(True);col.addWidget(self.monitor_message);self.cancel_button=self.button('cancelJob',self.cancel_job);col.addWidget(self.cancel_button);self.log=QPlainTextEdit();self.log.setObjectName('logs');self.log.setReadOnly(True);self.log.setMinimumHeight(100);col.addWidget(self.log,1);row.addWidget(frame,1);content.addLayout(row,1)
        content.addWidget(self.label('jobHistory','section'));self.job_table=self.table(5);self.job_table.setMinimumHeight(130);self.job_table.cellClicked.connect(self.select_job);content.addWidget(self.job_table)
        scroll.setWidget(body);layout.addWidget(scroll,1)

    def build_models(self):
        _,layout=self.make_page();self.heading(layout,'modelsEyebrow','modelsTitle','modelsDesc',self.button('importModel',self.import_model))
        self.model_empty=self.label('noModelsHint','notice',True);layout.addWidget(self.model_empty);self.model_table=self.table(8);layout.addWidget(self.model_table,1);layout.addWidget(self.label('exportHint','subtitle',True))

    @staticmethod
    def table(columns):
        table=QTableWidget(0,columns);table.verticalHeader().hide();table.setFocusPolicy(Qt.FocusPolicy.NoFocus);table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setAlternatingRowColors(True);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);table.horizontalHeader().setStretchLastSection(True);return table

    def project(self):return next((p for p in self.projects if p['id']==self.project_id),None)

    def persist(self):
        self.pref_path.write_text(json.dumps({'language':self.lang,'project':self.project_id,'sidebar_collapsed':bool(self.prefs.get('sidebar_collapsed'))},ensure_ascii=False),encoding='utf-8')

    def date(self,value):return datetime.fromisoformat(value).astimezone().strftime('%Y-%m-%d %H:%M')

    def default_name(self):
        p=self.project()
        return f"{p['name']}_{p['station']}_detect_v{sum(bool(m['job']) for m in self.models)+1:03}_{datetime.now():%Y%m%d}" if p else ''

    def error(self,exc):
        message=self.tr(exc.code) if isinstance(exc,AppError) else str(exc)
        if isinstance(exc,AppError) and exc.detail:message+='\n'+exc.detail
        QMessageBox.warning(self,self.tr('generalError'),message)

    def ask(self,key):
        dialog=QMessageBox(QMessageBox.Icon.Question,self.tr('confirm'),self.tr(key),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,self)
        dialog.button(QMessageBox.StandardButton.Yes).setText(self.tr('yes'));dialog.button(QMessageBox.StandardButton.No).setText(self.tr('no'));dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return dialog.exec()==QMessageBox.StandardButton.Yes

    def notify(self,key,**values):self.statusBar().showMessage(self.tr(key,**values),10000)

    @guarded
    def go(self,index):
        if hasattr(self,'canvas') and self.dirty:self.save()
        if index!=4 and self.project() is None:index=4
        self.stack.setCurrentIndex(index)
        self.update_navigation()
        for i,button in enumerate(self.nav):button.setChecked(i==index)
        self.dataset_nav.setChecked(index==5)
        if index==5:self.dataset_page.refresh()
        if index==1 and not self.current and self.images:self.load_image(self.filtered_images()[0] if self.filtered_images() else self.images[0])

    def update_navigation(self):
        inside=self.stack.currentIndex()!=4
        self.new_project_button.setVisible(not inside)
        for widget in (self.project_context_label,self.project_select,self.workflow_label,self.dataset_nav,*self.nav):widget.setVisible(inside)
        self.home_button.setChecked(not inside)
        self.project_title.setText(self.project()['name'] if inside and self.project() else self.tr('allProjects'))

    @guarded
    def change_language(self,index):
        self.lang=('zh-TW','zh-CN','en')[index]
        alive=[]
        for widget,key,setter in self.bindings:
            try:
                text=self.tr(key)
                if isinstance(widget,QPushButton):text=text.replace('&','&&')
                getattr(widget,setter)(text);alive.append((widget,key,setter))
            except RuntimeError:pass
        self.bindings=alive
        for i,key in enumerate(self.filter_keys):self.image_filter.setItemText(i,self.tr(key))
        self.device.setItemText(0,self.tr('deviceAuto'));self.canvas.empty_text=self.tr('canvasEmpty');self.canvas.update();self.setWindowTitle('YOLO Studio — '+self.tr('native'));self.image_signature=None;self.model_signature=None;self.persist();self.refresh();self.render_boxes()

    @guarded
    def change_project(self,index):
        identity=self.project_select.itemData(index)
        if identity==self.project_id or identity is None:return
        try:
            self.set_project(identity)
        except Exception:
            self.project_select.blockSignals(True);self.project_select.setCurrentIndex(self.project_select.findData(self.project_id));self.project_select.blockSignals(False);raise

    def set_project(self,identity):
        if identity==self.project_id:return
        self.store.get('projects',identity)
        if self.dirty:self.save()
        self.project_id=identity;self.current=None;self.canvas.load(None,[],[],[]);self.canvas.class_id=0;self.image_info.clear();self.image_signature=None;self.model_signature=None;self.train_name.clear();self.log_job=''
        self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False);self.image_filter.blockSignals(True);self.image_filter.setCurrentIndex(0);self.image_filter.blockSignals(False)
        self.dataset_page.search.blockSignals(True);self.dataset_page.search.clear();self.dataset_page.search.blockSignals(False);self.dataset_page.filter.blockSignals(True);self.dataset_page.filter.setCurrentIndex(0);self.dataset_page.filter.blockSignals(False)
        self.persist();self.refresh()
        if self.stack.currentIndex()==1 and self.images:self.load_image(self.images[0])

    @guarded
    def refresh(self):
        if self.importing:return
        summaries=self.store.project_summaries()
        self.projects=[{k:v for k,v in p.items() if k not in ('image_count','reviewed_count','model_count')} for p in summaries]
        if self.project_id not in [p['id'] for p in self.projects]:self.project_id=self.projects[0]['id'] if self.projects else ''
        options=[(self.project_select.itemData(i),self.project_select.itemText(i)) for i in range(self.project_select.count())]
        desired=[(p['id'],p['name']) for p in self.projects]
        if options!=desired:
            self.project_select.blockSignals(True);self.project_select.clear()
            for identity,name in desired:self.project_select.addItem(name,identity)
            self.project_select.setCurrentIndex(self.project_select.findData(self.project_id));self.project_select.blockSignals(False)
        elif self.project_select.currentData()!=self.project_id:
            self.project_select.blockSignals(True);self.project_select.setCurrentIndex(self.project_select.findData(self.project_id));self.project_select.blockSignals(False)
        self.images=self.store.list('images',self.project_id) if self.project_id else []
        # The library page reloads only while visible; it is refreshed again when opened.
        if self.stack.currentIndex()==5:self.dataset_page.refresh()
        self.models=self.store.list('models',self.project_id) if self.project_id else []
        self.jobs=self.store.list('jobs',self.project_id) if self.project_id else []
        p=self.project();self.update_navigation()
        self.render_project_cards(summaries)
        counts=[len(self.images),sum(im['status'] in ('reviewed','empty') for im in self.images),sum(im['status']=='pending' for im in self.images),len(self.models)]
        for widget,count in zip(self.stat_labels,counts):widget.setText(str(count))
        self.dataset_card_count.setText(self.tr('projectCardCounts',images=counts[0],reviewed=counts[1],models=counts[3]))
        if p:
            self.info_label.setText(f"{self.tr('projectName')}\n{p['name']}\n\n{self.tr('station')}  ·  {p['station']}\n{self.tr('created')}  ·  {self.date(p['created'])}\n\n{self.tr('classes')}\n"+' / '.join(p['classes']))
        else:self.info_label.setText(self.tr('noProjectHint'))
        available=self.manager.engine_available();self.engine_label.setText('●  '+self.tr('engineReady' if available else 'engineNotReady'));self.engine_notice.setVisible(not available)
        engine_info=os.environ.get('YOLO_STUDIO_ENGINE_INFO')
        if available and engine_info:
            selected=json.loads(engine_info)
            self.engine_label.setText('● '+selected.get('label','CPU')+'\n'+selected.get('device_name','CPU'))
            self.engine_label.setToolTip(selected.get('reason','')+' · Driver API '+str(selected.get('driver_api',0)))
        signature=[(im['id'],im['revision']) for im in self.images]
        if signature!=self.image_signature:self.image_signature=signature;self.render_images()
        if self.current and not self.dirty and not self.canvas.gesture:
            latest=next((im for im in self.images if im['id']==self.current['id']),None)
            if latest and latest['revision']!=self.current['revision']:self.load_image(latest)
            elif latest is None:self.current=None;self.canvas.load(None,[],[],p['classes'] if p else []);self.image_info.clear()
        class_names=p['classes'] if p else []
        self.render_classes()
        self.readiness.setText(self.tr('readiness',count=counts[1]));active=bool(self.manager.processes);self.train_button.setEnabled(available and counts[1]>=3 and not active)
        self.render_model_choices()
        default=self.default_name()
        if not self.train_name.text() or self.train_name.text()==self.last_default:self.train_name.setText(default)
        self.last_default=default
        model_signature=[(m['id'],m['name']) for m in self.models]
        if self.model_signature!=model_signature:self.model_signature=model_signature;self.render_models()
        self.render_jobs();self.render_boxes()

    def filtered_images(self):
        needle=self.search.text().lower();key=self.filter_keys[self.image_filter.currentIndex()]
        return [im for im in self.images if needle in im['name'].lower() and (key=='allImages' or im['status']==key)]

    def render_images(self,*args):
        """Update the image list in place; rebuilding 1,000+ items on every save made annotation lag."""
        images=self.filtered_images();ids=[im['id'] for im in images]
        existing=[self.image_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.image_list.count())]
        self.image_list.blockSignals(True)
        if ids!=existing:
            self.image_list.setUpdatesEnabled(False);self.image_list.clear()
            for im in images:
                if im['id'] not in self.thumbnails:self.thumbnails[im['id']]=thumbnail(self.store.path(im['path']),90,70)
                item=QListWidgetItem(self.thumbnails[im['id']],im['name']+'\n'+self.tr(im['status']));item.setData(Qt.ItemDataRole.UserRole,im['id']);item.setToolTip(im['name']);self.image_list.addItem(item)
            self.image_list.setUpdatesEnabled(True)
        else:
            for row,im in enumerate(images):
                text=im['name']+'\n'+self.tr(im['status']);item=self.image_list.item(row)
                if item.text()!=text:item.setText(text)
        self.sync_image_selection()
        self.image_list.blockSignals(False)

    def sync_image_selection(self):
        identity=self.current['id'] if self.current else None
        item=self.image_list.currentItem()
        if item is not None and item.data(Qt.ItemDataRole.UserRole)==identity:return
        blocked=self.image_list.blockSignals(True)
        for row in range(self.image_list.count()):
            if self.image_list.item(row).data(Qt.ItemDataRole.UserRole)==identity:
                self.image_list.setCurrentRow(row);self.image_list.scrollToItem(self.image_list.item(row));break
        self.image_list.blockSignals(blocked)

    @guarded
    def choose_image(self,item,previous=None):
        if not item:return
        identity=item.data(Qt.ItemDataRole.UserRole)
        if self.current and self.current['id']==identity:return
        if self.dirty:self.save()
        self.load_image(self.store.get('images',identity))

    def load_image(self,im):
        self.autosave.stop();self.current=copy.deepcopy(im);self.dirty=False;self.canvas.load(self.store.path(im['path']),im['boxes'],im['proposals'],self.project()['classes']);self.image_info.setText(im['name']+f" · {im['width']} × {im['height']} px");self.render_boxes();self.sync_image_selection()

    def annotation_edited(self):
        self.dirty=True;self.save_label.setText(self.tr('unsaved'));self.render_boxes();self.autosave.start()

    def render_boxes(self):
        self.box_list.blockSignals(True);self.box_list.clear()
        for i,b in enumerate(self.canvas.boxes):self.box_list.addItem(f"{i+1:02}   {self.project()['classes'][b['class_id']]}")
        self.box_list.setCurrentRow(self.canvas.selected);self.box_list.blockSignals(False)
        pending=bool(self.current and self.current['status']=='pending' and not self.canvas.handled)
        self.proposal_info.setVisible(pending);self.accept_button.setVisible(pending);self.accept_button.setEnabled(bool(self.canvas.proposals));self.proposal_info.setText(self.tr('candidateCount',count=len(self.canvas.proposals))+'\n'+self.tr('proposalHint'))
        for button in (self.review_button,self.draft_button,self.exclude_button):button.setEnabled(self.current is not None)
        self.save_label.setText(self.tr('unsaved' if self.dirty else 'saved') if self.current else '')
        self.selection_changed(self.canvas.selected)

    def selection_changed(self,index):
        self.box_list.blockSignals(True);self.box_list.setCurrentRow(index);self.box_list.blockSignals(False);self.box_class.setEnabled(index>=0);self.delete_button.setEnabled(index>=0)
        if 0<=index<len(self.canvas.boxes):self.box_class.blockSignals(True);self.box_class.setCurrentIndex(self.canvas.boxes[index]['class_id']);self.box_class.blockSignals(False)

    def select_box(self,index):self.canvas.selected=index;self.set_mode('select');self.selection_changed(index);self.canvas.update()
    def set_class(self,index):self.canvas.class_id=max(0,index)
    def change_box_class(self,index):
        if index>=0:self.canvas.change_class(index)
    def set_mode(self,mode):self.canvas.mode=mode;self.draw_button.setChecked(mode=='draw');self.select_button.setChecked(mode=='select')

    def save(self,reviewed=False,excluded=False):
        self.autosave.stop()
        if not self.current:return
        if self.canvas.gesture:self.autosave.start();return
        saved=self.store.save_image(self.current['id'],self.canvas.boxes,self.current['revision'],reviewed,excluded,self.canvas.handled)
        self.current=saved;self.dirty=False;self.canvas.proposals=copy.deepcopy(saved['proposals']);self.canvas.handled=False;self.canvas.update();self.image_signature=None;self.refresh()

    @guarded
    def save_draft(self,*args):self.save()

    @guarded
    def review(self):
        if self.canvas.proposals and not self.canvas.handled and not self.ask('discardProposalsConfirm'):return
        if not self.canvas.boxes and not self.ask('emptyReviewConfirm'):return
        self.save(reviewed=True);self.notify('saved')

    @guarded
    def exclude(self):self.save(excluded=True)
    def accept_proposals(self):self.canvas.accept();self.notify('proposalsAdded')

    @guarded
    def navigate(self,offset):
        images=self.filtered_images();index=next((i for i,im in enumerate(images) if self.current and im['id']==self.current['id']),-1)+offset
        if 0<=index<len(images):
            if self.dirty:self.save()
            self.load_image(images[index])

    @guarded
    def new_project(self):
        dialog=QDialog(self);dialog.setWindowTitle(self.tr('newProject'));dialog.resize(440,480);layout=QVBoxLayout(dialog);layout.setSpacing(14);layout.addWidget(self.label('projectDialogHint','subtitle',True));form=QFormLayout();form.setVerticalSpacing(12);form.setHorizontalSpacing(14);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow);name=QLineEdit();name.setMinimumHeight(34);station=QLineEdit();station.setMinimumHeight(34);classes=QPlainTextEdit();classes.setPlaceholderText('screw\ncap\nNOPASS');classes.setMaximumHeight(180);form.addRow(self.tr('projectName'),name);station.setPlaceholderText(self.tr('stationExample'));form.addRow(self.tr('stationOptional'),station);form.addRow(self.tr('classNames'),classes);layout.addLayout(form);layout.addWidget(self.label('classesLater','subtitle',True));buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr('createProject'));buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr('cancel'));buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if self.dirty:self.save()
        p=self.store.create_project(name.text(),station.text(),[line.strip() for line in classes.toPlainText().splitlines() if line.strip()]);self.set_project(p['id']);self.go(0);self.notify('projectCreated')

    @guarded
    def edit_project(self,identity=None):
        target_id=identity or self.project_id
        require(bool(target_id),'selectProjectFirst')
        proj=self.store.get('projects',target_id)
        dialog=QDialog(self);dialog.setWindowTitle(self.tr('editProject'));dialog.resize(420,230);layout=QVBoxLayout(dialog);layout.setSpacing(14)
        form=QFormLayout();form.setVerticalSpacing(12);form.setHorizontalSpacing(14);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        name=QLineEdit(proj['name']);name.setMinimumHeight(34);station=QLineEdit(proj['station']);station.setMinimumHeight(34);station.setPlaceholderText(self.tr('stationExample'))
        form.addRow(self.tr('projectName'),name);form.addRow(self.tr('stationOptional'),station);layout.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr('save'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr('cancel'))
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if self.dirty:self.save()
        updated=self.store.update_project(target_id,name.text(),station.text())
        self.project_card_signature=None;self.refresh();self.notify('projectUpdated',name=updated['name'])

    @guarded
    def delete_project(self,identity=None):
        target_id=identity or self.project_id
        require(bool(target_id),'selectProjectFirst')
        proj=self.store.get('projects',target_id)
        if not self.ask_custom(self.tr('deleteProjectConfirm',name=proj['name'])):return
        if self.dirty and self.project_id==target_id:
            self.autosave.stop();self.dirty=False
        for j in self.store.list('jobs',target_id):
            if j['id'] in self.manager.processes:
                self.manager.cancel(j['id'])
        self.store.delete_project(target_id)
        if self.project_id==target_id:
            self.project_id='';self.current=None;self.canvas.load(None,[],[],[]);self.image_info.clear();self.image_signature=None;self.model_signature=None
        self.project_card_signature=None;self.persist();self.refresh()
        if not self.project() or self.stack.currentIndex()==4:
            self.go(4)
        self.notify('projectDeleted',name=proj['name'])

    def prompt_add_class(self):
        if not self.project():return
        name, ok = QInputDialog.getText(self, self.tr('addClass'), self.tr('addClassPrompt'))
        if not ok or not name.strip():return
        name = name.strip()
        classes = list(self.project()['classes'])
        if name in classes:
            self.error(AppError('duplicate_classes'));return
        classes.append(name)
        if self.dirty:self.save()
        self.store.update_project_classes(self.project_id, classes)
        self.refresh()

    def manage_classes(self):
        self.prompt_add_class()

    def toggle_class_delete_mode(self, enabled):
        self.render_classes()

    def render_classes(self):
        p = self.project()
        class_names = p['classes'] if p else []
        if self.canvas.classes != class_names:
            self.canvas.classes = class_names
            self.canvas.update()
        del_mode = getattr(self, 'del_mode_btn', None) is not None and self.del_mode_btn.isChecked()
        current_idx = self.class_list.currentRow()
        self.class_list.blockSignals(True)
        self.class_list.clear()
        for i, name in enumerate(class_names):
            icon = QPixmap(10, 10)
            icon.fill(QColor(COLORS[i % len(COLORS)]))
            item = QListWidgetItem()
            item.setSizeHint(QSize(180, 38))
            self.class_list.addItem(item)
            w = QWidget()
            layout = QHBoxLayout(w)
            layout.setContentsMargins(6, 4, 6, 4)
            layout.setSpacing(6)
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon)
            layout.addWidget(icon_lbl)
            txt_lbl = QLabel(name)
            txt_lbl.setStyleSheet("font-weight: 500;")
            layout.addWidget(txt_lbl, 1)
            if del_mode:
                del_btn = QPushButton()
                del_btn.setIcon(ui_icon('trash', '#c0392b', 15))
                del_btn.setIconSize(QSize(15, 15))
                del_btn.setFixedSize(24, 24)
                del_btn.setToolTip(self.tr('delete'))
                del_btn.setStyleSheet("padding:0; margin:0; min-width:24px; max-width:24px; min-height:24px; max-height:24px; background:#fff0f0; border:1px solid #ffcccc; color:#cc3333; border-radius:4px;")
                del_btn.clicked.connect(lambda checked=False, idx=i, cname=name: self.delete_class(idx, cname))
                layout.addWidget(del_btn)
            self.class_list.setItemWidget(item, w)
        if class_names:
            target_row = max(0, min(current_idx if current_idx >= 0 else 0, len(class_names) - 1))
            self.class_list.setCurrentRow(target_row)
        self.class_list.blockSignals(False)

        self.box_class.blockSignals(True)
        self.box_class.clear()
        for i, name in enumerate(class_names):
            self.box_class.addItem(name)
        self.box_class.blockSignals(False)

    def delete_class(self, idx, name):
        if not self.ask_custom(self.tr('deleteClassConfirm', name=name)):return
        if self.dirty:self.save()
        self.store.delete_project_class(self.project_id, idx)
        self.refresh()

    def ask_custom(self, message):
        dialog=QMessageBox(QMessageBox.Icon.Question,self.tr('confirm'),message,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,self)
        dialog.button(QMessageBox.StandardButton.Yes).setText(self.tr('yes'));dialog.button(QMessageBox.StandardButton.No).setText(self.tr('no'));dialog.setDefaultButton(QMessageBox.StandardButton.No)
        return dialog.exec()==QMessageBox.StandardButton.Yes

    @guarded
    def import_dialog(self):
        if not self.project():self.new_project()
        if not self.project():return
        files,_=QFileDialog.getOpenFileNames(self,self.tr('importImages'),'','Images (*.jpg *.jpeg *.png *.bmp *.webp)')
        if files:self.import_paths(files)

    @guarded
    def import_folder(self):
        if not self.project():self.new_project()
        if not self.project():return
        folder=QFileDialog.getExistingDirectory(self,self.tr('importFolder'))
        if folder:self.import_paths([str(p) for p in sorted(Path(folder).iterdir()) if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.webp'}])

    @guarded
    def import_paths(self,paths):
        if self.importing:return
        if not self.project():raise AppError('selectProjectFirst')
        if self.dirty:self.save()
        files=[]
        for p in paths:
            candidate=Path(p)
            if candidate.is_dir():
                files.extend(sorted(c for c in candidate.iterdir() if c.is_file() and c.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.webp'}))
            elif candidate.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.webp'}:
                files.append(candidate)
        if not files:return
        label_files,class_map=self.store.prepare_yolo_import(self.project_id,files)
        progress=QProgressDialog(self.tr('importImages'),self.tr('cancel'),0,len(files),self);progress.setWindowModality(Qt.WindowModality.WindowModal);progress.setMinimumDuration(0);self.importing=True;count=duplicates=0;errors=[]
        try:
            for i,path in enumerate(files):
                progress.setValue(i);progress.setLabelText(self.tr('importProgress',current=i+1,total=len(files)));QApplication.processEvents()
                if progress.wasCanceled():break
                try:
                    require(path.stat().st_size<=25*1024*1024,'upload_too_large')
                    boxes=self.store.parse_yolo_boxes(label_files.get(path),class_map)
                    im=self.store.import_image(self.project_id,path.name,path.read_bytes(),boxes=boxes)
                    annotated=bool(im.get('annotated'))
                    duplicates+=int(bool(im.get('duplicate')) and not annotated)
                    count+=int(not im.get('duplicate') or annotated)
                except Exception as exc:errors.append(path.name+': '+(self.tr(exc.code) if isinstance(exc,AppError) else str(exc)))
        finally:self.importing=False;progress.setValue(len(files));progress.close();progress.deleteLater();self.image_signature=None;self.refresh()
        self.notify('importDone',count=count,duplicates=duplicates)
        if errors:QMessageBox.warning(self,self.tr('generalError'),self.tr('importErrors',count=len(errors))+'\n'+'\n'.join(errors[:10]))

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        if self.stack.currentIndex()==4:event.ignore();return
        self.import_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]);event.acceptProposedAction()

    def model_choices(self):return [('YOLO11n',('model','yolo11n.pt')),('YOLO11s',('model','yolo11s.pt')),('YOLOv10n',('model','yolov10n.pt'))]+[(m['name'],('model_id',m['id'])) for m in self.models]

    def model_matches_project(self,key,value):
        p=self.project()
        if not p or not p.get('classes'):return False
        project_classes=set(p['classes'])
        if key=='model':
            return bool(project_classes & COCO_CLASSES)
        if key=='model_id':
            m=next((m for m in self.models if m['id']==value),None)
            if not m:return False
            model_classes=m.get('metadata',{}).get('classes')
            if model_classes is None:return True
            return bool(project_classes & set(model_classes))
        return True

    def prompt_train_first(self,model_name,key=None,value=None):
        p=self.project()
        classes_str=' / '.join(p['classes']) if p and p.get('classes') else '—'
        reviewed=[im for im in self.images if im['status'] in ('reviewed','empty')]
        can_train=len(reviewed)>=3 and any(im['boxes'] for im in reviewed) and not self.manager.processes
        hint=self.tr('trainFirstReadyHint',reviewed=len(reviewed)) if can_train else self.tr('trainFirstNeedImagesHint',reviewed=len(reviewed))
        msg=self.tr('trainFirstPrompt',model=model_name,classes=classes_str)+'\n\n'+hint
        dialog=QMessageBox(QMessageBox.Icon.Question,self.tr('classMismatchTitle'),msg,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,self)
        dialog.button(QMessageBox.StandardButton.Yes).setText(self.tr('trainNowBtn') if can_train else self.tr('goTrainCenterBtn'))
        dialog.button(QMessageBox.StandardButton.No).setText(self.tr('cancel'))
        dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
        if dialog.exec()==QMessageBox.StandardButton.Yes:
            if key and value:
                idx=self.train_model.findData((key,value))
                if idx>=0:self.train_model.setCurrentIndex(idx)
            self.go(2)
            if can_train:self.start_training()

    def render_model_choices(self):
        choices=self.model_choices();existing=[(self.train_model.itemText(i),self.train_model.itemData(i)) for i in range(self.train_model.count())]
        if choices!=existing:
            selected=self.train_model.currentData();self.train_model.clear()
            for name,value in choices:self.train_model.addItem(name,value)
            index=self.train_model.findData(selected)
            if index>=0:self.train_model.setCurrentIndex(index)

    @guarded
    def auto_dialog(self):
        require(self.project() is not None,'selectProjectFirst');require(self.manager.engine_available(),'engine_missing')
        if self.dirty:self.save()
        dialog=QDialog(self);dialog.setWindowTitle(self.tr('autoLabel'));dialog.resize(500,360);layout=QVBoxLayout(dialog);layout.setSpacing(14);layout.addWidget(self.label('autoHint','subtitle',True))
        form=QFormLayout();form.setVerticalSpacing(12);form.setHorizontalSpacing(14);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        model=QComboBox();model.setMinimumHeight(36)
        default_idx=0
        for i,(name,value) in enumerate(self.model_choices()):
            model.addItem(name,value)
            if value[0]=='model_id' and self.model_matches_project(value[0],value[1]):
                default_idx=i
        model.setCurrentIndex(default_idx)
        confidence=QDoubleSpinBox();confidence.setRange(.01,.99);confidence.setSingleStep(.05);confidence.setValue(.4);confidence.setMinimumHeight(36)
        form.addRow(self.tr('selectModel'),model);form.addRow(self.tr('confidence'),confidence);layout.addLayout(form);layout.addWidget(self.label('classMappingHint','notice',True))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr('startAuto'));buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr('cancel'));buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            key,value=model.currentData()
            if not self.model_matches_project(key,value):
                self.prompt_train_first(model.currentText(),key,value)
                return
            job=self.manager.start(self.project_id,'autolabel',{key:value,'confidence':confidence.value(),'device':'auto'});self.log_job=job['id'];self.refresh();self.go(2);self.notify('jobStarted')

    @guarded
    def start_training(self):
        require(self.project() is not None,'selectProjectFirst')
        name_val = self.train_name.text().strip() or self.default_name()
        self.train_name.setText(name_val)
        key,value=self.train_model.currentData();cfg={key:value,'name':name_val,'epochs':self.epochs.value(),'imgsz':int(self.imgsz.currentText()),'batch':self.batch.value(),'device':self.device.currentData()};job=self.manager.start(self.project_id,'train',cfg);self.log_job=job['id'];self.refresh();self.notify('jobStarted')

    def select_job(self,row,column):
        if 0<=row<len(self.jobs):self.log_job=self.jobs[row]['id'];self.render_jobs()

    def render_jobs(self):
        self.job_table.setHorizontalHeaderLabels([self.tr(k) for k in ('modelName','taskType','created','status','progressLabel')]);self.job_table.setRowCount(len(self.jobs))
        for row,job in enumerate(self.jobs):
            values=[job['config'].get('name',self.tr('autolabel')),self.tr('training' if job['kind']=='train' else 'autolabel'),self.date(job['created']),self.tr(job['status']),f"{job['progress']:.0%}"]
            for col,value in enumerate(values):self.job_table.setItem(row,col,QTableWidgetItem(value))
            self.job_table.setRowHeight(row,44)
        running_job = next((j for j in self.jobs if j['status'] in ('running','queued')), None)
        if running_job:
            job = running_job
            self.log_job = running_job['id']
        else:
            job = next((j for j in self.jobs if j['id']==self.log_job), self.jobs[0] if self.jobs else None)
        if not job:self.monitor_title.setText(self.tr('noActiveJob'));self.monitor_message.clear();self.progress.setValue(0);self.cancel_button.setEnabled(False);self.log.clear();return
        self.log_job=job['id']
        for r, j in enumerate(self.jobs):
            if j['id'] == job['id']:
                self.job_table.blockSignals(True)
                self.job_table.setCurrentCell(r, 0)
                self.job_table.blockSignals(False)
                break
        self.monitor_title.setText(job['config'].get('name',self.tr('autolabel'))+' · '+self.tr(job['status']));self.progress.setValue(round(job['progress']*100))
        if job['message']=='class_mismatch':
            p=self.project()
            classes_str=' / '.join(p['classes']) if p and p.get('classes') else '—'
            message=self.tr('classMismatchShort',classes=classes_str)
        else:
            message=self.tr(job['message']) if job['message'] in MESSAGES else job['message']
            if job['result'].get('detail'):
                detail=str(job['result']['detail'])
                if len(detail)>220:detail=detail[:220]+'…'
                message+='\n'+detail
        if job['kind']=='autolabel' and job['status']=='completed':message+='\n'+self.tr('processedSummary',**job['result'])
        self.monitor_message.setText(message);self.cancel_button.setEnabled(job['status'] in ('queued','running'));log=self.manager.log(job['id'])
        if log!=self.log.toPlainText():self.log.setPlainText(log);self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    @guarded
    def cancel_job(self):
        if self.log_job and self.ask('cancelConfirm'):self.manager.cancel(self.log_job);self.refresh()

    @guarded
    def import_model(self):
        require(self.project() is not None,'selectProjectFirst');path,_=QFileDialog.getOpenFileName(self,self.tr('importModel'),'','YOLO (*.pt)')
        if not path:return
        source=Path(path);require(source.stat().st_size<=300*1024*1024,'upload_too_large');dest=self.store.path(f'models/{uid()}.pt');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);self.store.register_model(self.project_id,source.stem,dest,metadata={'source':'imported','classes':None});self.refresh();self.notify('modelImported')

    def render_models(self):
        self.model_empty.setVisible(not self.models);self.model_table.setHorizontalHeaderLabels([self.tr(k) for k in ('modelName','created','precision','recall','map50','map50_95','classes','exportModel')]);self.model_table.setRowCount(len(self.models))
        for row,model in enumerate(self.models):
            metrics=model['metadata'].get('metrics',{});values=[model['name'],self.date(model['created'])]+[f"{metrics[k]:.1%}" if k in metrics else '—' for k in ('precision','recall','map50','map50_95')]+[' / '.join(model['metadata'].get('classes') or []) or self.tr('imported')]
            for col,value in enumerate(values):self.model_table.setItem(row,col,QTableWidgetItem(value))
            button=QPushButton(self.tr('exportModel').replace('&','&&'));button.clicked.connect(lambda checked=False,identity=model['id']:self.export_model(identity));self.model_table.setCellWidget(row,7,button);self.model_table.setRowHeight(row,55)

    @guarded
    def export_model(self,identity):
        model=self.store.get('models',identity);path,_=QFileDialog.getSaveFileName(self,self.tr('exportModel'),model['name']+'.zip','ZIP (*.zip)')
        if not path:return
        destination=Path(path)
        if destination.suffix.lower()!='.zip':destination=destination.with_name(destination.name+'.zip')
        archive=self.store.model_package(identity,destination.stem);shutil.copy2(archive,destination);self.notify('fileSaved',path=destination)

    @guarded
    def export_dataset(self):
        require(self.project() is not None,'selectProjectFirst')
        # Validate before opening the save dialog.
        reviewed=[im for im in self.images if im['status'] in ('reviewed','empty')];require(len(reviewed)>=3,'need_reviewed_images');require(any(im['boxes'] for im in reviewed),'need_positive_labels')
        path,_=QFileDialog.getSaveFileName(self,self.tr('exportDataset'),self.project()['name']+'_dataset.zip','ZIP (*.zip)')
        if not path:return
        destination=Path(path)
        if destination.suffix.lower()!='.zip':destination=destination.with_name(destination.name+'.zip')
        folder=self.store.path(f'exports/{uid()}/dataset');self.store.snapshot(self.project_id,folder);yaml=folder/'data.yaml';yaml.write_text('\n'.join(['path: .',*yaml.read_text(encoding='utf-8').splitlines()[1:]])+'\n',encoding='utf-8')
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
            for file in folder.rglob('*'):
                if file.is_file():z.write(file,file.relative_to(folder).as_posix())
        self.notify('fileSaved',path=destination)

    def shortcuts(self):
        # Canvas-only shortcuts do not interfere with typing in filenames or forms.
        for key,callback in [('B',lambda:self.set_mode('draw')),('V',lambda:self.set_mode('select')),('Delete',self.canvas.delete_selected),('Ctrl+Z',self.canvas.undo),('Ctrl+S',self.save_draft),('Left',lambda:self.navigate(-1)),('Right',lambda:self.navigate(1))]:
            shortcut=QShortcut(QKeySequence(key),self.canvas);shortcut.setContext(Qt.ShortcutContext.WidgetShortcut);shortcut.activated.connect(callback)
        toggle_sb=QShortcut(QKeySequence('Ctrl+B'),self);toggle_sb.setContext(Qt.ShortcutContext.WindowShortcut);toggle_sb.activated.connect(self.toggle_sidebar)

    def closeEvent(self,event):
        if self.manager.processes and not self.ask('stopOnClose'):event.ignore();return
        try:
            if self.dirty:self.save()
            self.persist();self.manager.close();event.accept()
        except Exception as exc:self.error(exc);event.ignore()
