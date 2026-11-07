"""Prepare a Linux x86_64 runtime bundle; reuse existing models and licensed samples."""
import hashlib,json,os,platform,shutil,subprocess,sys,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(*args,env=None):subprocess.run([str(x) for x in args],cwd=ROOT,env=env,check=True)
def download(url,path,sha=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.is_file():
  tmp=path.with_suffix('.part');urllib.request.urlretrieve(url,tmp);tmp.replace(path)
 if sha and hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise SystemExit('SHA256 mismatch: '+str(path))
if sys.version_info<(3,9):raise SystemExit('Python 3.9 or newer is required')
if platform.system()!='Linux' or platform.machine() not in ['x86_64','amd64']:raise SystemExit('This package targets Linux x86_64')
for command in ['ffmpeg','ffprobe','cmake','gcc','g++']:
 if not shutil.which(command):raise SystemExit('Install prerequisite: '+command)
web=ROOT/'data/final_runtime/bin/python'
if not web.exists():run(sys.executable,'-m','venv',ROOT/'data/final_runtime')
run(web,'-m','pip','install','-r','requirements.txt')
speech=ROOT/'.venv-v2/bin/python'
if not speech.exists():run('bash','scripts/setup_v2.sh',env=dict(os.environ,PYTHON_BIN=sys.executable))
else:run(sys.executable,'scripts/download_models.py')
model_env=dict(os.environ,TORCH_HOME=str(ROOT/'models/torch'))
run(speech,'-c','from demucs.pretrained import get_model; get_model("htdemucs")',env=model_env)
chain=json.loads((ROOT/'deploy/toolchain.json').read_text());source=ROOT/'data/tools/llama.cpp';binary=source/'build-gcc9/bin/llama-server'
if not binary.is_file():
 archive=ROOT/'data/tools/llama.cpp.tar.gz';download('https://codeload.github.com/ggml-org/llama.cpp/tar.gz/'+chain['llamaCppCommit'],archive)
 source.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive) as tar:
  for member in tar.getmembers():
   parts=Path(member.name).parts[1:]
   if not parts:continue
   if member.issym() or member.islnk() or '..' in parts or not (member.isfile() or member.isdir()):continue
   member.name=str(Path(*parts));tar.extract(member,source)
 compiler=['-DCMAKE_C_COMPILER=/usr/bin/gcc-9','-DCMAKE_CXX_COMPILER=/usr/bin/g++-9'] if Path('/usr/bin/gcc-9').exists() else []
 run('cmake','-S',source,'-B',source/'build-gcc9',*compiler,'-DGGML_CUDA=OFF','-DLLAMA_CURL=OFF','-DLLAMA_BUILD_TESTS=OFF','-DCMAKE_BUILD_TYPE=Release')
 run('cmake','--build',source/'build-gcc9','--target','llama-server','-j','4')
cf=chain['cloudflared'];download(cf['url'],ROOT/'data/deploy/tools/cloudflared',cf['sha256']);(ROOT/'data/deploy/tools/cloudflared').chmod(0o755)
if not (ROOT/'fixtures/real_tao_v2/canonical.mp4').exists() or not (ROOT/'fixtures/real_ying_v2/canonical.mp4').exists():run(web,'scripts/prepare_real_samples.py')
if not (ROOT/'fixtures/interview_intro_v1/canonical.mp4').exists():run(web,'scripts/prepare_sample.py')
print('Prepared. Run: python deploy/manage.py build && python deploy/manage.py install')
