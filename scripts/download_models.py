"""Resume public model downloads with bounded ranged transfers and SHA256 checks."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
CATALOG={
 'asr':('Systran/faster-whisper-medium','faster-whisper-medium',['config.json','tokenizer.json','vocabulary.txt','model.bin']),
 'llm':('Qwen/Qwen2.5-7B-Instruct-GGUF','qwen2.5-7b',['qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf','qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf'])}

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def download(repo,revision,name,folder,metadata,workers):
 dest=folder/name;folder.mkdir(parents=True,exist_ok=True)
 size=metadata.get('lfs',{}).get('size') or metadata.get('size')
 expected=metadata.get('lfs',{}).get('sha256')
 if dest.exists() and (not size or dest.stat().st_size==size) and (not expected or digest(dest)==expected):
  print('Verified',name,flush=True);return
 url='https://huggingface.co/'+repo+'/resolve/'+revision+'/'+name
 part=dest.with_name(dest.name+'.part')
 if not size or size<16*1024*1024:
  urllib.request.urlretrieve(url,part)
 else:
  start=part.stat().st_size if part.exists() else 0
  if start>size:raise RuntimeError('Unexpected partial size for '+name)
  chunk_dir=folder/(name+'.ranges');chunk_dir.mkdir(exist_ok=True)
  chunk_size=16*1024*1024
  ranges=[(a,min(size-1,a+chunk_size-1)) for a in range(start,size,chunk_size)]
  done=[start]
  def get_chunk(bounds):
   a,b=bounds;path=chunk_dir/('%d-%d'%(a,b))
   if path.exists() and path.stat().st_size==b-a+1:return path
   for attempt in range(3):
    try:
     request=urllib.request.Request(url,headers={'Range':'bytes=%d-%d'%(a,b)})
     with urllib.request.urlopen(request,timeout=120) as r:
      if r.status!=206 or not r.headers.get('Content-Range','').startswith('bytes %d-%d/'%(a,b)):
       raise RuntimeError('Server did not honor the requested byte range')
      with path.open('wb') as f:shutil.copyfileobj(r,f,1024*1024)
     if path.stat().st_size!=b-a+1:raise RuntimeError('Incomplete chunk')
     done[0]+=b-a+1
     print(name,round(done[0]*100/size,1),'%',flush=True)
     return path
    except Exception:
     if attempt==2:raise
     time.sleep(1+attempt)
  with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:paths=list(pool.map(get_chunk,ranges))
  with part.open('ab') as f:
   for p in paths:
    with p.open('rb') as source:shutil.copyfileobj(source,f,1024*1024)
  if part.stat().st_size!=size:raise RuntimeError('Unexpected downloaded size')
 if expected and digest(part)!=expected:raise RuntimeError('Model SHA256 mismatch; retained partial file for diagnosis')
 part.replace(dest)
 print('Ready',name,flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=['asr','llm','all'],default='all');p.add_argument('--workers',type=int,default=8);args=p.parse_args()
 records=[]
 for kind,(repo,folder,names) in CATALOG.items():
  if args.kind not in ['all',kind]:continue
  with urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true',timeout=60) as response:meta=json.load(response)
  siblings={i['rfilename']:i for i in meta['siblings']}
  for name in names:
   download(repo,meta['sha'],name,ROOT/'models'/folder,siblings[name],max(1,min(8,args.workers)))
   records.append({'repo':repo,'revision':meta['sha'],'file':folder+'/'+name,'sha256':digest(ROOT/'models'/folder/name)})
 out=ROOT/'models'/('manifest-'+args.kind+'.json');out.write_text(json.dumps(records,indent=2)+'\n')
