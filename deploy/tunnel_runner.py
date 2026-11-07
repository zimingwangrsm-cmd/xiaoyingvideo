"""Run the HTTPS connector under systemd and persist its current, non-secret public URL."""
import argparse,datetime,json,os,re,signal,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--origin',required=True);p.add_argument('--state',required=True);p.add_argument('--log',required=True);a=p.parse_args()
state=Path(a.state);state.parent.mkdir(parents=True,exist_ok=True);current={'url':None,'status':'starting','origin':a.origin}
def save():
 current['updatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();temp=state.with_suffix('.tmp');temp.write_text(json.dumps(current,indent=2)+'\n');temp.replace(state)
save();child=subprocess.Popen([a.binary,'tunnel','--no-autoupdate','--protocol','http2','--url',a.origin],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
def stop(*_):child.terminate()
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
with open(a.log,'a',buffering=1) as log:
 for line in child.stdout:
  log.write(line);print(line,end='',flush=True)
  match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',line)
  if match:current['url']=match[0];save()
  if 'Registered tunnel connection' in line:current['status']='connected';save()
code=child.wait();current['status']='stopped';save();sys.exit(code or 1)
