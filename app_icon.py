"""Qt and Win32 title-bar icons owned by the application process."""
import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon,QPixmap

BASE=Path(__file__).resolve().parent
_native_handles={}


def application_icon():
    icon=QIcon()
    source=QPixmap(str(BASE/'assets/app-icon.png'))
    for size in (16,20,24,32,40,48,64,128,256):
        icon.addPixmap(source.scaled(QSize(size,size)))
    return icon


def set_native_icon(hwnd):
    if sys.platform!='win32':return False
    import ctypes
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.LoadImageW.argtypes=[wintypes.HINSTANCE,wintypes.LPCWSTR,wintypes.UINT,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    user.LoadImageW.restype=wintypes.HANDLE
    user.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    user.SendMessageW.restype=ctypes.c_ssize_t
    handles=[]
    for kind,metric in ((0,49),(1,11)):
        size=user.GetSystemMetrics(metric)
        handle=user.LoadImageW(None,str(BASE/'assets/app-icon.ico'),1,size,size,0x10)
        if handle:user.SendMessageW(hwnd,0x80,kind,handle);handles.append(handle)
    old=_native_handles.pop(int(hwnd),[])
    for handle in old:user.DestroyIcon(wintypes.HICON(handle))
    _native_handles[int(hwnd)]=handles
    return len(handles)==2


