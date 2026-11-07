"""Build an isolated release and operate only this project's user-level systemd units."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DEPLOY=ROOT/'data/deploy';UNITS=['koubo-demo-model.service','koubo-demo-web.service','koubo-demo-tunnel.service']
def systemctl(*args):
 env=dict(os.environ,XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/'+str(os.getuid())+'/bus')
 return subprocess.run(['systemctl','--user',*args],env=env,check=True)
def q(value):return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'
def selected():
 paths=[]
 for folder,extensions in [('backend',{'.py'}),('frontend/dist-hosted' if (ROOT/'frontend/dist-hosted').exists() else 'frontend/dist',{'.js','.css','.html'}),('deploy',{'.py','.sh','.json','.md','.example'}),('fixtures',{'.json','.srt','.mp4','.jpg','.md'})]:
  for p in (ROOT/folder).rglob('*'):
   if p.is_file() and p.suffix in extensions and '__pycache__' not in p.parts and '_work' not in p.parts:paths.append(p)
 for name in ['scripts/speech_worker.py','scripts/download_models.py','scripts/setup_v2.sh','scripts/run_local_model.sh','scripts/prepare_real_samples.py','scripts/prepare_sample.py','requirements.txt','requirements-dev.txt','requirements-speech-lock.txt','requirements-speech.txt','README_V2.md','deliverables/v2/runtime_manifest.json']:
  paths.append(ROOT/name)
 return sorted(set(paths))
def build(a):
 if (ROOT/'frontend/build.mjs').is_file():
  env=dict(os.environ,BUILD_DIR='dist-hosted');subprocess.run(['node','frontend/build.mjs'],cwd=ROOT,env=env,check=True)
 elif not (ROOT/'frontend/dist/index.html').is_file():raise SystemExit('Prebuilt frontend is missing')
 paths=selected();hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
 release=DEPLOY/'releases'/digest[:16]
 if not release.exists():
  release.mkdir(parents=True)
  for p in paths:
   rel=p.relative_to(ROOT)
   if str(rel).startswith('frontend/dist-hosted/'):rel=Path('frontend/dist')/p.relative_to(ROOT/'frontend/dist-hosted')
   target=release/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
  (release/'models').symlink_to(ROOT/'models',target_is_directory=True)
  (release/'RELEASE.json').write_text(json.dumps({'sourceSha256':digest,'files':hashes},indent=2)+'\n')
 python=Path(a.python).absolute();speech=ROOT/'.venv-v2/bin/python';binary=ROOT/'data/tools/llama.cpp/build-gcc9/bin/llama-server';model=ROOT/'models/qwen2.5-7b/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf';tunnel=DEPLOY/'tools/cloudflared'
 for p in [python,speech,binary,model,tunnel,ROOT/'models/faster-whisper-medium/model.bin',ROOT/'models/torch/hub/checkpoints/955717e8-8726e21a.th']:
  if not p.is_file():raise SystemExit('Required runtime missing: '+str(p))
 units=DEPLOY/'systemd';units.mkdir(parents=True,exist_ok=True);runtime=DEPLOY/'runtime';runtime.mkdir(exist_ok=True);data=DEPLOY/'public-data';data.mkdir(exist_ok=True)
 common='\nRestart=always\nRestartSec=5\nTimeoutStartSec=240\nTimeoutStopSec=120\nUMask=0077\nNoNewPrivileges=true\n\n[Install]\nWantedBy=default.target\n'
 model_cmd=[binary,'-m',model,'--host','127.0.0.1','--port',str(a.model_port),'-c','16384','-t','8','-tb','8','-ngl','0','--parallel','1','--alias','qwen-local']
 (units/UNITS[0]).write_text('[Unit]\nDescription=Koubo demo local Qwen model\nStartLimitIntervalSec=0\n\n[Service]\nType=simple\nWorkingDirectory='+str(release)+'\nExecStart='+' '.join(map(q,model_cmd))+'\nExecStartPost='+' '.join(map(q,[python,release/'deploy/wait_ready.py',f'http://127.0.0.1:{a.model_port}/health']))+common)
 variables={'APP_MODE':'hosted','ALLOW_UPLOADS':'true','DATA_DIR':str(data),'FRONTEND_DIST':str(release/'frontend/dist'),'SPEECH_PYTHON':str(speech),'ASR_MODEL':str(ROOT/'models/faster-whisper-medium'),'LOCAL_LLM_URL':f'http://127.0.0.1:{a.model_port}/v1','DEMO_TEST_FAILURES':'false','MAX_UPLOAD_MB':'90','MAX_SOURCE_SECONDS':'180','HOSTED_MAX_PROJECTS':'50','HOSTED_PROJECTS_PER_SESSION':'10','HOSTED_MAX_JOBS':'3','HOSTED_STORAGE_MB':'10240'}
 web_cmd=[python,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',str(a.port),'--workers','1','--proxy-headers','--forwarded-allow-ips','127.0.0.1','--no-access-log']
 (units/UNITS[1]).write_text('[Unit]\nDescription=Koubo full-feature hosted web demo\nWants='+UNITS[0]+'\nAfter='+UNITS[0]+'\nStartLimitIntervalSec=0\n\n[Service]\nType=simple\nWorkingDirectory='+str(release)+'\n'+''.join('Environment='+q(k+'='+v)+'\n' for k,v in variables.items())+'ExecStart='+' '.join(map(q,web_cmd))+'\nExecStartPost='+' '.join(map(q,[python,release/'deploy/wait_ready.py',f'http://127.0.0.1:{a.port}/api/ready']))+common)
 tunnel_cmd=[python,release/'deploy/tunnel_runner.py','--binary',tunnel,'--origin',f'http://127.0.0.1:{a.port}','--state',runtime/'tunnel.json','--log',runtime/'tunnel.log']
 (units/UNITS[2]).write_text('[Unit]\nDescription=Koubo public HTTPS demo connector\nWants='+UNITS[1]+'\nAfter='+UNITS[1]+'\nStartLimitIntervalSec=0\n\n[Service]\nType=simple\nWorkingDirectory='+str(release)+'\nExecStart='+' '.join(map(q,tunnel_cmd))+common)
 config={'release':str(release),'sourceSha256':digest,'python':str(python),'port':a.port,'modelPort':a.model_port,'dataDirectory':str(data),'units':UNITS};(DEPLOY/'deployment.json').write_text(json.dumps(config,indent=2)+'\n')
 package=DEPLOY/'koubo-web-runtime.tar.gz'
 with tarfile.open(package,'w:gz') as tar:
  for p in paths:
   rel=p.relative_to(ROOT)
   if str(rel).startswith('frontend/dist-hosted/'):rel=Path('frontend/dist')/p.relative_to(ROOT/'frontend/dist-hosted')
   tar.add(p,arcname=Path('koubo-web')/rel)
  tar.add(release/'RELEASE.json',arcname='koubo-web/RELEASE.json')
 print(json.dumps({'release':str(release),'package':str(package),'packageBytes':package.stat().st_size,'sourceSha256':digest},indent=2))
def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['build','install','status','restart-web','stop']);p.add_argument('--python',default=str(ROOT/'data/final_runtime/bin/python'));p.add_argument('--port',type=int,default=8768);p.add_argument('--model-port',type=int,default=8783);a=p.parse_args()
 if a.command=='build':build(a)
 elif a.command=='install':
  for name in UNITS:systemctl('link',str(DEPLOY/'systemd'/name))
  systemctl('daemon-reload');systemctl('enable',*UNITS);systemctl('restart',*UNITS)
 elif a.command=='restart-web':systemctl('restart',UNITS[1]);systemctl('start',UNITS[2])
 elif a.command=='stop':systemctl('stop',*reversed(UNITS))
 else:
  systemctl('status',*UNITS,'--no-pager','-l')
  if (DEPLOY/'runtime/tunnel.json').exists():print((DEPLOY/'runtime/tunnel.json').read_text())
if __name__=='__main__':main()
