"""Download CUDA wheels with the hashes published by the official PyTorch index."""
import concurrent.futures
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from download_network import configure

ROOT=Path('D:/YOLOStudio-CUDA-Build')


def fetch(item):
    path=ROOT/'wheels'/item['filename'];path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
        if digest==item['sha256']:return str(path)
        raise RuntimeError('Existing wheel hash mismatch: '+str(path))
    if int(item['bytes'])>64*1024*1024:return segmented(item,path)
    part=path.with_suffix('.part');start=time.monotonic();last=start;size=0;digest=hashlib.sha256()
    with urllib.request.urlopen(item['url'],timeout=120) as response,part.open('wb') as output:
        while block:=response.read(4*1024*1024):
            output.write(block);digest.update(block);size+=len(block)
            if time.monotonic()-last>=20:
                print(f"{item['profile']} {item['package']}: {size/1024**2:.0f} MiB ({size/max(1,time.monotonic()-start)/1024**2:.1f} MiB/s)",flush=True);last=time.monotonic()
    if digest.hexdigest()!=item['sha256']:raise RuntimeError('Downloaded wheel hash mismatch: '+str(path))
    part.rename(path);print('Verified '+path.name,flush=True);return str(path)


def segmented(item,path):
    total=int(item['bytes']);count=16;chunk=(total+count-1)//count
    directory=path.parent/(path.name+'.segments');directory.mkdir(exist_ok=True)
    partial=path.with_suffix('.part')
    if partial.exists() and partial.stat().st_size<=chunk and not (directory/'0').exists():partial.rename(directory/'0')
    def segment(index):
        start=index*chunk;end=min(total,start+chunk)-1;dest=directory/str(index)
        for attempt in range(5):
            received=dest.stat().st_size if dest.exists() else 0
            if received==end-start+1:return
            request=urllib.request.Request(item['url']+f'?segment={start+received}-{end}',headers={'Range':f'bytes={start+received}-{end}','Accept-Encoding':'identity'})
            try:
                with urllib.request.urlopen(request,timeout=120) as response:
                    expected=f'bytes {start+received}-{end}/{total}'
                    if response.status!=206 or response.headers.get('Content-Range')!=expected:raise RuntimeError('Server did not honor byte range')
                    with dest.open('ab') as output:
                        while block:=response.read(65536):output.write(block)
                if dest.stat().st_size!=end-start+1:raise RuntimeError('Incomplete segment')
                print(f"{item['profile']}: segment {index+1}/{count} downloaded",flush=True);return
            except Exception:
                if attempt==4:raise
                time.sleep(attempt+1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
        pending=[pool.submit(segment,index) for index in range(count)]
        while pending:
            done,remaining=concurrent.futures.wait(pending,timeout=20,return_when=concurrent.futures.FIRST_EXCEPTION)
            for task in done:task.result()
            pending=list(remaining)
            size=sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
            print(f"{item['profile']} total: {size/1024**2:.0f}/{total/1024**2:.0f} MiB",flush=True)
    digest=hashlib.sha256()
    with partial.open('wb') as out:
        for index in range(count):
            with (directory/str(index)).open('rb') as source:
                while block:=source.read(4*1024*1024):out.write(block);digest.update(block)
    if digest.hexdigest()!=item['sha256']:raise RuntimeError('Official SHA256 verification failed')
    partial.rename(path);print('Verified '+path.name,flush=True);return str(path)


def fetch_remaining(items,workers=128):
    """Resume existing ranges with smaller parallel requests and a shared worker limit."""
    tasks=[];assemblies=[]
    for item in items:
        path=ROOT/'wheels'/item['filename']
        if path.exists():
            fetch(item);continue
        if int(item['bytes'])<=64*1024*1024:
            fetch(item);continue
        total=int(item['bytes']);chunk=(total+15)//16
        directory=path.parent/(path.name+'.segments');directory.mkdir(parents=True,exist_ok=True)
        partial=path.with_suffix('.part')
        if partial.exists() and partial.stat().st_size<=chunk and not (directory/'0').exists():partial.rename(directory/'0')
        pieces=[]
        for index in range(16):
            start=index*chunk;end=min(total,start+chunk);prefix=directory/str(index)
            size=prefix.stat().st_size if prefix.exists() else 0
            if size>end-start:raise RuntimeError('Invalid existing range size')
            if size:pieces.append(prefix)
            for offset in range(start+size,end,8*1024*1024):
                dest=directory/f'{index}-{offset}';stop=min(end,offset+8*1024*1024)
                pieces.append(dest);tasks.append((item,dest,offset,stop,total))
        assemblies.append((item,path,pieces))
    def request_piece(task):
        item,dest,start,end,total=task
        for attempt in range(12):
            size=dest.stat().st_size if dest.exists() else 0
            if size==end-start:return
            if size>end-start:raise RuntimeError('Invalid downloaded range size')
            # Both endpoints are official PyTorch distribution hosts.
            url=item['url'] if attempt%2==0 else item['url'].replace('download-r2.pytorch.org','download.pytorch.org')
            req=urllib.request.Request(url+f'?range={start+size}-{end-1}',headers={'Range':f'bytes={start+size}-{end-1}','Accept-Encoding':'identity'})
            try:
                with urllib.request.urlopen(req,timeout=45) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start+size}-{end-1}/{total}':raise RuntimeError('Unexpected range response')
                    with dest.open('ab') as output:
                        while block:=response.read(65536):output.write(block)
                if dest.stat().st_size!=end-start:raise RuntimeError('Incomplete range')
                return
            except Exception:
                if attempt==11:raise
                time.sleep(min(attempt+1,5))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        pending=set(pool.submit(request_piece,t) for t in tasks)
        while pending:
            done,pending=concurrent.futures.wait(pending,timeout=20,return_when=concurrent.futures.FIRST_EXCEPTION)
            for future in done:future.result()
            for item,path,pieces in assemblies:
                size=sum(p.stat().st_size for p in pieces if p.exists())
                print(f"{item['profile']}: {size/1024**2:.0f}/{int(item['bytes'])/1024**2:.0f} MiB",flush=True)
    for item,path,pieces in assemblies:
        part=path.with_suffix('.part');digest=hashlib.sha256()
        with part.open('wb') as out:
            for piece in pieces:
                with piece.open('rb') as source:
                    while block:=source.read(4*1024*1024):out.write(block);digest.update(block)
        if digest.hexdigest()!=item['sha256']:raise RuntimeError('Official wheel SHA256 verification failed: '+path.name)
        part.rename(path);print('Verified '+path.name,flush=True)


if __name__=='__main__':
    configure()
    parser=argparse.ArgumentParser();parser.add_argument('--build-root',type=Path,default=ROOT);args=parser.parse_args();ROOT=args.build_root.resolve()
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest=ROOT/'download-plan.json'
    if not manifest.exists():manifest.write_text((Path(__file__).resolve().parents[1]/'packaging/cuda-wheels.json').read_text(),encoding='utf-8')
    items=json.loads(manifest.read_text())
    fetch_remaining(items)
