"""Native image library and non-destructive image preparation."""
import io
from pathlib import Path

from PySide6.QtCore import QSize,Qt,QTimer
from PySide6.QtGui import QIcon,QImage,QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,QApplication,QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,
    QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListView,QListWidget,QListWidgetItem,
    QMessageBox,QProgressDialog,QPushButton,QSpinBox,QSplitter,QVBoxLayout,QWidget,
)
from core import AppError,require
from canvas import thumbnail


TEXT={
    'datasetTitle':['圖片資料集','图片数据集','Image dataset'],
    'datasetEyebrow':['圖片管理','图片管理','IMAGE LIBRARY'],
    'datasetDescription':['瀏覽與整理圖片，進行清洗、預處理，再前往標註。','浏览与整理图片，进行清洗、预处理，再前往标注。','Browse, clean and prepare images before annotation.'],
    'manageDataset':['管理圖片資料集 →','管理图片数据集 →','Manage image dataset →'],
    'datasetCardHint':['點進資料集，瀏覽、預處理、新增或移除圖片。','进入数据集，浏览、预处理、新增或移除图片。','Open the dataset to browse, prepare, add or remove images.'],
    'selectedImages':['已選取 {count} 張','已选择 {count} 张','{count} images selected'],
    'trash':['回收區','回收区','Trash'],
    'removeImages':['移至回收區','移到回收区','Move to trash'],
    'restoreImages':['還原圖片','恢复图片','Restore images'],
    'removeConfirm':['將 {count} 張圖片移至回收區？可隨時還原，既有訓練快照不受影響。','将 {count} 张图片移到回收区？可随时恢复，已有训练快照不受影响。','Move {count} images to trash? They can be restored; existing training snapshots are unaffected.'],
    'preprocess':['圖片預處理','图片预处理','Prepare images'],
    'audit':['檢查圖片','检查图片','Check images'],
    'auditResult':['共 {total} 張，{valid} 張正常，{bad} 張有問題。','共 {total} 张，{valid} 张正常，{bad} 张有问题。','{total} images: {valid} valid, {bad} with problems.'],
    'previewImage':['選取圖片以預覽','选择图片以预览','Select an image to preview'],
    'openAnnotation':['開啟標註','打开标注','Open annotation'],
    'no_selection':['請先選取圖片','请先选择图片','Select images first'],
    'image_removed':['圖片已移至回收區，請先還原','图片已移到回收区，请先恢复','Restore this image from trash first'],
    'need_source_groups':['訓練至少需要 3 組獨立來源圖片；原圖與預處理副本算同一組','训练至少需要 3 组独立来源图片；原图与预处理副本算同一组','Training requires 3 independent source groups. Originals and prepared copies count as one group'],
    'invalid_crop':['裁切範圍超出圖片，請調整座標與尺寸','裁剪范围超出图片，请调整坐标与尺寸','Crop bounds exceed the image. Adjust position and size'],
    'operation':['處理方式','处理方式','Operation'],
    'rotate':['順時針旋轉 90°','顺时针旋转 90°','Rotate 90° clockwise'],
    'flip':['水平翻轉','水平翻转','Flip horizontally'],
    'grayscale':['灰階','灰度','Grayscale'],
    'autocontrast':['自動對比','自动对比度','Auto contrast'],
    'brightness':['調整亮度','调整亮度','Brightness'],
    'resize':['調整尺寸','调整尺寸','Resize'],
    'crop':['裁切（單張）','裁剪（单张）','Crop (one image)'],
    'longEdge':['最長邊（像素）','最长边（像素）','Longest edge (px)'],
    'factor':['亮度倍率','亮度倍数','Brightness factor'],
    'cropX':['左側 X','左侧 X','Left X'],
    'cropY':['上方 Y','上方 Y','Top Y'],
    'cropW':['寬度','宽度','Width'],
    'cropH':['高度','高度','Height'],
    'before':['原圖','原图','Original'],
    'after':['處理預覽（第一張）','处理预览（第一张）','Preview (first image)'],
    'saveCopies':['另存處理後副本','另存处理后副本','Save prepared copies'],
    'processingHint':['原圖保留；副本沿用並轉換人工框，需重新審核。原圖與副本在訓練切分時維持同組。','保留原图；副本沿用并转换人工框，需重新审核。原图与副本在训练划分时保持同组。','Originals are retained. Manual boxes are transformed; copies need review. Source families stay together when splitting datasets.'],
    'processedResult':['新增 {count} 張副本，略過 {duplicates} 張相同圖片。','新增 {count} 张副本，跳过 {duplicates} 张相同图片。','Created {count} copies; skipped {duplicates} duplicates.'],
    'previewFailed':['無法預覽此圖片','无法预览此图片','Cannot preview this image'],
    'backDashboard':['← 專案工作台','← 项目工作台','← Project dashboard'],
}


def pixmap(image):
    buffer=io.BytesIO();image.save(buffer,format='PNG')
    return QPixmap.fromImage(QImage.fromData(buffer.getvalue()))


class PrepareDialog(QDialog):
    def __init__(self,owner,images):
        super().__init__(owner);self.owner=owner;self.images=images;self.setWindowTitle(owner.tr('preprocess'));self.resize(960,650)
        layout=QVBoxLayout(self);layout.setSpacing(16);layout.addWidget(owner.label('processingHint','notice',True))
        self.operations=('rotate','flip','grayscale','autocontrast','brightness','resize','crop')
        self.operation=QComboBox()
        for key in self.operations:
            if key!='crop' or len(images)==1:self.operation.addItem(owner.tr(key),key)
        form=QFormLayout();form.addRow(owner.tr('operation'),self.operation)
        self.edge=QSpinBox();self.edge.setRange(64,8192);self.edge.setValue(1024);form.addRow(owner.tr('longEdge'),self.edge)
        self.factor=QDoubleSpinBox();self.factor.setRange(.2,3);self.factor.setSingleStep(.1);self.factor.setValue(1.2);form.addRow(owner.tr('factor'),self.factor)
        self.crop_controls={}
        for key,label,default,maximum in [('x','cropX',0,images[0]['width']-1),('y','cropY',0,images[0]['height']-1),('w','cropW',images[0]['width'],images[0]['width']),('h','cropH',images[0]['height'],images[0]['height'])]:
            spin=QSpinBox();spin.setRange(0 if key in ('x','y') else 1,maximum);spin.setValue(default);self.crop_controls[key]=spin;form.addRow(owner.tr(label),spin)
        self.form=form;layout.addLayout(form)
        row=QHBoxLayout();self.original=QLabel();self.result=QLabel()
        for key,preview in [('before',self.original),('after',self.result)]:
            col=QVBoxLayout();col.addWidget(owner.label(key,'section'));preview.setMinimumSize(280,230);preview.setAlignment(Qt.AlignmentFlag.AlignCenter);preview.setStyleSheet('background:#e9efed;border:1px solid #d5e3dc;border-radius:8px;');col.addWidget(preview,1);row.addLayout(col,1)
        layout.addLayout(row,1);self.error_label=QLabel();self.error_label.setWordWrap(True);layout.addWidget(self.error_label)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText(owner.tr('saveCopies'));buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(owner.tr('cancel'));self.ok=buttons.button(QDialogButtonBox.StandardButton.Ok);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.setInterval(180);self.preview_timer.timeout.connect(self.update_preview)
        self.operation.currentIndexChanged.connect(self.changed)
        for control in (self.edge,self.factor,*self.crop_controls.values()):control.valueChanged.connect(self.changed)
        self.original_pixmap=QPixmap(str(owner.store.path(images[0]['path'])));self.changed()

    def options(self):
        return {'edge':self.edge.value(),'factor':self.factor.value(),**{k:v.value() for k,v in self.crop_controls.items()}}

    def changed(self,*args):
        operation=self.operation.currentData()
        for widget,visible in [(self.edge,operation=='resize'),(self.factor,operation=='brightness'),*[(w,operation=='crop') for w in self.crop_controls.values()]]:
            widget.setVisible(visible);self.form.labelForField(widget).setVisible(visible)
        self.ok.setEnabled(False);self.preview_timer.start()

    def update_preview(self):
        try:
            image,_,_=self.owner.store.prepare_image(self.images[0]['id'],self.operation.currentData(),self.options())
            self.result_pixmap=pixmap(image);self.error_label.clear();self.ok.setEnabled(True);self.scale_previews()
        except Exception as exc:
            self.result.clear();self.error_label.setText(self.owner.tr(exc.code) if isinstance(exc,AppError) else str(exc));self.ok.setEnabled(False)

    def scale_previews(self):
        self.original.setPixmap(self.original_pixmap.scaled(self.original.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        if hasattr(self,'result_pixmap'):self.result.setPixmap(self.result_pixmap.scaled(self.result.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'original_pixmap'):self.scale_previews()

    def done(self,result):
        self.preview_timer.stop()
        super().done(result)


class DatasetPage(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.signature=None;self.images=[];self.icons={}
        layout=QVBoxLayout(self);layout.setContentsMargins(30,26,30,24);layout.setSpacing(18)
        owner.heading(layout,'datasetEyebrow','datasetTitle','datasetDescription',owner.button('importImages',owner.import_dialog,True))
        tools=QHBoxLayout();tools.addWidget(owner.button('backDashboard',lambda:owner.go(0)));tools.addWidget(owner.button('importFolder',owner.import_folder));self.search=QLineEdit();owner.bind(self.search,'searchImages','setPlaceholderText');tools.addWidget(self.search,1);self.filter=QComboBox();self.filter_keys=('allImages','unlabeled','draft','pending','reviewed','empty','excluded','trash');self.filter.addItems([owner.tr(k) for k in self.filter_keys]);tools.addWidget(self.filter);layout.addLayout(tools)
        row=QHBoxLayout();self.selection_label=QLabel();row.addWidget(self.selection_label,1);row.addWidget(owner.button('audit',self.audit));self.prepare_button=owner.button('preprocess',self.prepare);row.addWidget(self.prepare_button);self.remove_button=owner.button('removeImages',lambda:self.trash(True));row.addWidget(self.remove_button);self.restore_button=owner.button('restoreImages',lambda:self.trash(False));row.addWidget(self.restore_button);layout.addLayout(row)
        splitter=QSplitter();splitter.setChildrenCollapsible(False);self.list=QListWidget();self.list.setViewMode(QListView.ViewMode.IconMode);self.list.setResizeMode(QListView.ResizeMode.Adjust);self.list.setMovement(QListView.Movement.Static);self.list.setIconSize(QSize(148,108));self.list.setGridSize(QSize(180,170));self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.list.setWordWrap(True);splitter.addWidget(self.list)
        detail=QWidget();col=QVBoxLayout(detail);self.preview=QLabel(owner.tr('previewImage'));self.preview.setMinimumSize(260,230);self.preview.setMaximumHeight(360);self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setStyleSheet('background:#e8eeeb;border-radius:8px;');col.addWidget(self.preview);self.details=QLabel();self.details.setWordWrap(True);self.details.setTextFormat(Qt.TextFormat.PlainText);col.addWidget(self.details);self.annotate_button=owner.button('openAnnotation',self.open_annotation,True);col.addWidget(self.annotate_button);col.addStretch();splitter.addWidget(detail);splitter.setSizes([800,280]);splitter.setStretchFactor(0,1);layout.addWidget(splitter,1)
        self.search.textChanged.connect(self.refresh);self.filter.currentIndexChanged.connect(self.refresh);self.list.itemSelectionChanged.connect(self.selection_changed);self.list.itemDoubleClicked.connect(lambda item:self.open_annotation())

    def selected(self):
        ids={item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()}
        return [im for im in self.images if im['id'] in ids]

    def refresh(self,*args):
        owner=self.owner
        for i,key in enumerate(self.filter_keys):self.filter.setItemText(i,owner.tr(key))
        self.images=owner.store.list('images',owner.project_id,include_deleted=True) if owner.project_id else []
        key=self.filter_keys[self.filter.currentIndex()];needle=self.search.text().lower();visible=[im for im in self.images if bool(im['deleted'])==(key=='trash') and (key in ('allImages','trash') or im['status']==key) and needle in im['name'].lower()]
        signature=(owner.project_id,owner.lang,key,needle,tuple((im['id'],im['revision']) for im in visible))
        if signature!=self.signature:
            selected={im['id'] for im in self.selected()};self.signature=signature;self.list.blockSignals(True)
            ids=[im['id'] for im in visible];existing=[self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]
            if ids==existing:
                # Only names/status changed: update text without reloading thumbnails.
                for row,im in enumerate(visible):
                    text=im['name']+'\n'+owner.tr('trash' if im['deleted'] else im['status']);item=self.list.item(row)
                    if item.text()!=text:item.setText(text)
            else:
                self.list.setUpdatesEnabled(False);self.list.clear()
                for im in visible:
                    if im['id'] not in self.icons:self.icons[im['id']]=thumbnail(owner.store.path(im['path']),160,120)
                    item=QListWidgetItem(self.icons[im['id']],im['name']+'\n'+owner.tr('trash' if im['deleted'] else im['status']));item.setData(Qt.ItemDataRole.UserRole,im['id']);item.setToolTip(im['name']);self.list.addItem(item);item.setSelected(im['id'] in selected)
                self.list.setUpdatesEnabled(True)
            self.list.blockSignals(False)
        self.selection_changed()

    def selection_changed(self):
        owner=self.owner;selected=self.selected();trash=self.filter_keys[self.filter.currentIndex()]=='trash';self.selection_label.setText(owner.tr('selectedImages',count=len(selected)));self.remove_button.setVisible(not trash);self.restore_button.setVisible(trash)
        for button in (self.remove_button,self.restore_button):button.setEnabled(bool(selected))
        self.prepare_button.setEnabled(bool(selected) and not trash);self.annotate_button.setEnabled(len(selected)==1 and not trash)
        if selected:
            im=selected[0];self.preview.setPixmap(QPixmap(str(owner.store.path(im['path']))).scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));self.details.setText(f"{im['name']}\n{im['width']} × {im['height']} px\n{owner.tr('trash' if im['deleted'] else im['status'])}\n{owner.tr('boxes')}: {len(im['boxes'])}")
        else:self.preview.setText(owner.tr('previewImage'));self.details.clear()

    def open_annotation(self):
        selected=self.selected()
        if len(selected)!=1 or selected[0]['deleted']:return
        owner=self.owner
        try:
            if owner.dirty:owner.save()
            owner.go(1);owner.load_image(owner.store.get('images',selected[0]['id']))
        except Exception as exc:owner.error(exc)

    def trash(self,deleted):
        owner=self.owner;selected=self.selected()
        if not selected:return
        if deleted and QMessageBox.question(owner,owner.tr('confirm'),owner.tr('removeConfirm',count=len(selected)),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:
            if owner.dirty:owner.save()
            ids=[im['id'] for im in selected];owner.store.trash_images(owner.project_id,ids,deleted)
            if owner.current and owner.current['id'] in ids:owner.current=None;owner.canvas.load(None,[],[],owner.project()['classes']);owner.image_info.clear()
            owner.refresh()
        except Exception as exc:owner.error(exc)

    def prepare(self):
        owner=self.owner;selected=self.selected()
        if not selected:return
        try:
            if owner.dirty:owner.save()
            dialog=PrepareDialog(owner,selected)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            progress=QProgressDialog(owner.tr('preprocess'),owner.tr('cancel'),0,len(selected),owner);progress.setWindowModality(Qt.WindowModality.WindowModal);progress.setMinimumDuration(0);owner.importing=True;count=duplicates=0;errors=[]
            try:
                for i,im in enumerate(selected):
                    progress.setValue(i);QApplication.processEvents()
                    if progress.wasCanceled():break
                    try:
                        result=owner.store.process_image(im['id'],dialog.operation.currentData(),dialog.options());duplicates+=int(bool(result.get('duplicate')));count+=int(not result.get('duplicate'))
                    except Exception as exc:errors.append(im['name']+': '+str(exc))
            finally:owner.importing=False;progress.setValue(len(selected));progress.close();progress.deleteLater();owner.refresh()
            owner.notify('processedResult',count=count,duplicates=duplicates)
            if errors:QMessageBox.warning(owner,owner.tr('generalError'),'\n'.join(errors[:10]))
        except Exception as exc:owner.error(exc)

    def audit(self):
        owner=self.owner
        try:
            result=owner.store.audit_images(owner.project_id);message=owner.tr('auditResult',total=result['total'],valid=result['valid'],bad=len(result['problems']))
            if result['problems']:message+='\n\n'+'\n'.join(p['name']+' · '+p['detail'] for p in result['problems'][:20])
            QMessageBox.information(owner,owner.tr('audit'),message)
        except Exception as exc:owner.error(exc)
