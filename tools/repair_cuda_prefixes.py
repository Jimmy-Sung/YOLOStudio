"""Repair ranges left by the earlier eight-range download layout.

The current downloader uses sixteen ranges. Legacy range 1..7 started at a
different offset, so their preserved prefixes must be fetched again. Range zero
and new ranges 8..15 have unchanged origins. Full official SHA256 remains the
release gate after this repair.
"""
import concurrent.futures
import json
import shutil
import time
import urllib.request
from pathlib import Path
from download_network import configure

ROOT=Path('D:/YOLOStudio-CUDA-Build')


def main():
    configure()
    items=json.loads((ROOT/'download-plan.json').read_text())
    jobs=[];groups=[]
    directory=ROOT/'prefix-repair';directory.mkdir(exist_ok=True)
    for item in items:
        if item['package']!='torch':continue
        chunk=(int(item['bytes'])+15)//16
        for index in range(1,8):
            original=ROOT/'wheels'/(item['filename']+'.segments')/str(index)
            size=original.stat().st_size;pieces=[]
            for relative in range(0,size,4*1024*1024):
                start=index*chunk+relative;end=index*chunk+min(size,relative+4*1024*1024)
                path=directory/f"{item['profile']}-{index}-{relative}"
                pieces.append(path);jobs.append((item,path,start,end))
            groups.append((original,pieces))
    def fetch(job):
        item,path,start,end=job
        for attempt in range(30):
            received=path.stat().st_size if path.exists() else 0
            if received==end-start:return
            if received>end-start:raise RuntimeError('Oversized repair range')
            url=item['url'] if attempt%2==0 else item['url'].replace('download-r2.pytorch.org','download.pytorch.org')
            req=urllib.request.Request(url+f'?repair={start+received}-{end-1}',headers={'Range':f'bytes={start+received}-{end-1}'})
            try:
                with urllib.request.urlopen(req,timeout=45) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f"bytes {start+received}-{end-1}/{item['bytes']}":raise RuntimeError('Invalid repair range response')
                    with path.open('ab') as output:
                        while block:=response.read(65536):output.write(block)
                if path.stat().st_size!=end-start:raise RuntimeError('Incomplete repair range')
                return
            except Exception:
                if attempt==29:raise
                time.sleep(min(5,attempt+1))
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        pending=set(pool.submit(fetch,job) for job in jobs)
        while pending:
            done,pending=concurrent.futures.wait(pending,timeout=20,return_when=concurrent.futures.FIRST_EXCEPTION)
            for future in done:future.result()
            got=sum(job[1].stat().st_size for job in jobs if job[1].exists());total=sum(job[3]-job[2] for job in jobs)
            print(f'Repair: {got/1024**2:.0f}/{total/1024**2:.0f} MiB',flush=True)
    for original,pieces in groups:
        temporary=original.with_suffix('.repair')
        with temporary.open('wb') as output:
            for piece in pieces:
                with piece.open('rb') as source:shutil.copyfileobj(source,output,4*1024*1024)
        if temporary.stat().st_size!=original.stat().st_size:raise RuntimeError('Repair size mismatch')
        temporary.replace(original)
    print('Legacy prefixes repaired; rerun fetch_cuda_wheels.py for official SHA256 verification.',flush=True)


if __name__=='__main__':main()
