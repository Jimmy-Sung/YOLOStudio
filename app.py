"""Native Qt desktop entry point. No HTML, web server or embedded browser."""
import argparse
import hashlib
import os
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
from runtime_paths import default_data_dir


def main():
    parser=argparse.ArgumentParser(description='YOLO Studio desktop')
    parser.add_argument('--data',type=Path,default=default_data_dir())
    args=parser.parse_args()
    args.data.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR',str(args.data.resolve()/'runtime/yolo'))
    os.environ.setdefault('MPLCONFIGDIR',str(args.data.resolve()/'runtime/matplotlib'))
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    from desktop import MainWindow
    from core import Store
    from jobs import JobManager
    from app_icon import application_icon,set_native_icon
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('YOLOStudio.Desktop')
    app=QApplication(sys.argv)
    app.setApplicationName('YOLO Studio');app.setOrganizationName('YOLOStudio')
    app.setWindowIcon(application_icon())
    name='YOLOStudio-'+hashlib.sha256(os.path.normcase(str(args.data.resolve())).encode()).hexdigest()[:20]
    socket=QLocalSocket();socket.connectToServer(name)
    if socket.waitForConnected(300):
        socket.write(b'activate');socket.waitForBytesWritten(300);return 0
    server=QLocalServer();QLocalServer.removeServer(name)
    if not server.listen(name):raise RuntimeError('Could not acquire application session lock')
    JobManager.terminate_lingering_workers()
    store=Store(args.data);manager=JobManager(store);window=MainWindow(store,manager)
    def activate():
        peer=server.nextPendingConnection()
        if peer:peer.disconnectFromServer()
        window.setWindowIcon(application_icon())
        set_native_icon(int(window.winId()))
        window.showNormal();window.raise_();window.activateWindow()
    server.newConnection.connect(activate);app.aboutToQuit.connect(manager.close)
    window.show()
    QTimer.singleShot(0,lambda:set_native_icon(int(window.winId())))
    return app.exec()


if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        import traceback
        message=traceback.format_exc()
        error_dir=default_data_dir()/'runtime';error_dir.mkdir(parents=True,exist_ok=True)
        (error_dir/'startup-error.log').write_text(message,encoding='utf-8')
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'無法啟動 / 无法启动 / Could not start\n\n'+message,'YOLO Studio',0x10)
        else:raise
