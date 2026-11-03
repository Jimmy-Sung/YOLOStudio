"""Cache IPv4 DNS results inside the wheel downloader, without system changes."""
import socket
import threading
import time


def configure():
    original=socket.getaddrinfo
    cache={};lock=threading.Lock()
    def lookup(host,port,family=0,type=0,proto=0,flags=0):
        if not host or not str(host).endswith('.pytorch.org'):
            return original(host,port,family,type,proto,flags)
        key=(host,port,type,proto,flags)
        with lock:
            record=cache.get(key)
            if record and time.monotonic()-record[0]<600:return record[1]
            result=original(host,port,socket.AF_INET,type,proto,flags)
            cache[key]=(time.monotonic(),result)
            return result
    socket.getaddrinfo=lookup
