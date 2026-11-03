"""Render the editable SVG and package native Windows icon resolutions."""
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PIL import Image
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

BASE=Path(__file__).resolve().parents[1]


def main():
    app=QApplication.instance() or QApplication([])
    renderer=QSvgRenderer(str(BASE/'assets/app-icon.svg'))
    if not renderer.isValid():raise RuntimeError('Invalid SVG icon')
    image=QImage(1024,1024,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter,QRectF(0,0,1024,1024));painter.end()
    target=BASE/'assets/app-icon.png'
    if not image.save(str(target)):raise RuntimeError('Could not save PNG icon')
    with Image.open(target) as source:
        source.save(BASE/'assets/app-icon.ico',format='ICO',sizes=[(n,n) for n in (16,20,24,32,40,48,64,128,256)])
    print('Created assets/app-icon.png and assets/app-icon.ico')


if __name__=='__main__':main()
