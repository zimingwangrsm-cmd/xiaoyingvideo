"""Start the real app and run HTTP acceptance in a permitted local terminal.

No privilege changes, public listeners, downloads or external uploads are used.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from select_port import select_port


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--check-only', action='store_true', help='Stop our server after the HTTP check.')
    args = parser.parse_args()
    os.chdir(ROOT)
    # Fail immediately on denied sockets, before starting children or changing state.
    try:
        port = select_port(args.port)
    except (OSError, ValueError, RuntimeError) as exc:
        print('当前终端不能创建本地监听端口：%s' % exc, file=sys.stderr)
        print('请使用允许本地网络的普通终端；本脚本不会提权或绕过策略。', file=sys.stderr)
        return 2
    subprocess.run(['npm', 'run', 'build'], cwd=ROOT/'frontend', check=True)
    subprocess.run([sys.executable, 'scripts/check_env.py'], check=True)
    if not (ROOT/'fixtures/interview_intro_v1/canonical.mp4').is_file():
        subprocess.run([sys.executable, 'scripts/prepare_sample.py'], check=True)
    directory = ROOT/'deliverables'
    directory.mkdir(exist_ok=True)
    log_path = directory/'local_server.log'
    receipt_path = directory/'local_run_receipt.json'
    url = 'http://127.0.0.1:%d' % port
    receipt = {'startedAt':time.strftime('%Y-%m-%d %H:%M:%S'), 'url':url,
               'httpAcceptance':'not_run', 'browserAcceptance':'pending',
               'operationRecording':'pending', 'serverRunning':False}
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    process = None
    # Loopback acceptance must not be routed through a workstation HTTP proxy.
    local_client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with log_path.open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app',
                                        '--host','127.0.0.1','--port',str(port),'--workers','1'],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            receipt['pid'] = process.pid
            ready = False
            for _ in range(40):
                if process.poll() is not None:
                    raise RuntimeError('服务启动失败，请查看deliverables/local_server.log。')
                try:
                    with local_client.open(url+'/api/health', timeout=1) as response:
                        ready = response.status == 200
                except (urllib.error.URLError, TimeoutError):
                    pass
                if ready:
                    break
                time.sleep(.5)
            if not ready:
                raise RuntimeError('服务未在20秒内就绪，请检查日志。')
            receipt['serverRunning'] = True
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
            result = subprocess.run([sys.executable, 'scripts/check_http.py', '--url', url],
                                    cwd=ROOT, capture_output=True, text=True, timeout=400)
            (directory/'http_check_console.log').write_text(result.stdout+result.stderr, encoding='utf-8')
            receipt['httpAcceptance'] = 'passed' if result.returncode == 0 else 'failed'
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
            print(result.stdout, flush=True)
            if result.returncode:
                raise RuntimeError('HTTP验收未通过，详见deliverables/http_check_console.log。')
            print('HTTP检查通过。浏览器入口：'+url, flush=True)
            print('验收记录已保存：deliverables/http_validation.json', flush=True)
            if args.check_only:
                return 0
            print('服务保持运行；按Ctrl+C停止本脚本启动的服务。浏览器交互与录屏仍需完成。', flush=True)
            return process.wait()
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        receipt['error'] = str(exc)
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        receipt['serverRunning'] = False
        receipt['stoppedAt'] = time.strftime('%Y-%m-%d %H:%M:%S')
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
