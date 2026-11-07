"""Verify recovery of this project's idle web unit, never unrelated processes."""
import datetime,json,os,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];config=json.loads((ROOT/'data/deploy/deployment.json').read_text());runtime=ROOT/'data/deploy/runtime'
for folder in ['jobs','processing']:
 for p in (Path(config['dataDirectory'])/folder).glob('*.json'):
  if json.loads(p.read_text()).get('status') in ['queued','running']:raise SystemExit('Active job exists; wait before recovery test')
for p in (Path(config['dataDirectory'])/'projects').glob('*/state.json'):
 if json.loads(p.read_text()).get('state')=='preparing':raise SystemExit('Active import exists; wait before recovery test')
env=dict(os.environ,XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/'+str(os.getuid())+'/bus')
def prop(name):return subprocess.check_output(['systemctl','--user','show','koubo-demo-web.service','--value','-p',name],env=env).decode().strip()
old=int(prop('MainPID'));assert old>0 and prop('ActiveState')=='active';url=json.loads((runtime/'tunnel.json').read_text())['url']
subprocess.run(['systemctl','--user','kill','--kill-who=main','--signal=SIGKILL','koubo-demo-web.service'],env=env,check=True)
start=time.monotonic();op=urllib.request.build_opener(urllib.request.ProxyHandler({}));new=old
while time.monotonic()-start<60:
 try:
  new=int(prop('MainPID'))
  with op.open('http://127.0.0.1:'+str(config['port'])+'/api/ready',timeout=2) as r:
   if new and new!=old and r.status==200:break
 except Exception:pass
 time.sleep(1)
else:raise SystemExit('Automatic web recovery failed')
assert json.loads((runtime/'tunnel.json').read_text())['url']==url
r={'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'webMainPidChanged':new!=old,'systemdRestarts':int(prop('NRestarts')),'readyAfterSeconds':round(time.monotonic()-start,2),'publicUrlUnchanged':True,'url':url,'method':'Killed only the named idle demo web main process; systemd Restart=always restored it, model/tunnel remained running.'}
(ROOT/'deliverables/deployment/recovery_validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
