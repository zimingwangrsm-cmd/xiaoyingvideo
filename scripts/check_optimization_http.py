"""Real local/public HTTP checks; new projects use isolated anonymous sessions."""
import argparse,hashlib,http.cookiejar,json,urllib.request,urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8767');p.add_argument('--public-url',default='http://127.0.0.1:8773');args=p.parse_args()
checks=[]
def client(base):
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def call(path,body=None,headers=None,raw=None):
  h=headers or {};data=raw
  if body is not None:data=json.dumps(body).encode();h={**h,'Content-Type':'application/json'}
  req=urllib.request.Request(base+path,data=data,headers=h)
  try:return opener.open(req,timeout=120)
  except urllib.error.HTTPError as e:return e
 return call
local=client(args.url);public=client(args.public_url)
health=json.load(local('/api/health'));assert health['status']=='ok' and health['mode']=='local'
project=json.load(local('/api/projects/from-sample',{'sampleId':'real_tao_v2'}));assert project['edit']['targetMs']==60000 and set(project['edit']['lockedBlockIds'])=={'s01','s03'} and project['edit']['brief']
checks.append('local health and visible Tao editing preset')
r=local('/api/projects/'+project['id']+'/actions',{'expectedRevision':project['revision'],'action':{'type':'set_brief','text':'保留完整语言背景，省略活动介绍'}});assert r.status==200
project=json.load(r);r=local('/api/projects/'+project['id']+'/transcript/restore',{'expectedRevision':project['revision'],'snapshotId':'a'*32});assert r.status==404
checks.append('editing brief action and owned snapshot restore route')
assert local('/delivery').status==200
index=json.load(local('/api/deliverables'))['artifacts'];assert {'before','after','package','optimization','current-recording'}<={a['id'] for a in index}
for a in index:
 r=local(a['url']);assert r.status==200
 h=hashlib.sha256();size=0
 while True:
  data=r.read(1024*1024)
  if not data:break
  h.update(data);size+=len(data)
 assert h.hexdigest()==a['sha256'] and size==a['bytes'],a['id']
checks.append('every delivery allowlist file downloaded and matched live SHA256/size')
r=local('/api/deliverables/after',headers={'Range':'bytes=0-31'});assert r.status==206 and len(r.read())==32
r=local('/api/deliverables/not-allowed');assert r.status==404
checks.append('delivery MP4 Range 206 and unknown key 404')
assert json.load(public('/api/health'))['allowUploads'] is False
assert public('/delivery').status==404 and public('/api/deliverables').status==404 and public('/api/deliverables/after').status==404
pub=json.load(public('/api/projects/from-sample',{'sampleId':'real_tao_v2'}))
# Valid multipart syntax reaches service policy without creating any uploaded file.
boundary='optimizationcheck';parts=[]
for name,value in [('expectedRevision',pub['revision']),('blockId','s02'),('keepBackground','false')]:parts.append('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+str(value)+'\r\n')
parts.append('--'+boundary+'\r\nContent-Disposition: form-data; name="audio"; filename="rejected.wav"\r\nContent-Type: audio/wav\r\n\r\nno persisted data\r\n--'+boundary+'--\r\n')
r=public('/api/projects/'+pub['id']+'/recordings',headers={'Content-Type':'multipart/form-data; boundary='+boundary},raw=''.join(parts).encode())
assert r.status==403 and json.load(r)['error']['code']=='uploads_disabled'
folder=Path('data/optimization_public/projects')/pub['id']/'recordings'
assert not folder.exists()
checks.append('public multipart recording returns403 with no persistent recording directory; delivery routes return404')
Path('deliverables/optimization/http_validation.json').write_text(json.dumps({'checks':checks,'deliveryFiles':len(index),'localMode':health['mode'],'publicMode':'public','note':'Actual current-version HTTP requests; source server only listens on loopback.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(checks,ensure_ascii=False,indent=2))
