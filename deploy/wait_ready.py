import argparse,time,urllib.request
p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--timeout',type=int,default=180);a=p.parse_args()
op=urllib.request.build_opener(urllib.request.ProxyHandler({}));deadline=time.monotonic()+a.timeout
while time.monotonic()<deadline:
 try:
  with op.open(a.url,timeout=3) as r:
   if r.status==200:raise SystemExit(0)
 except SystemExit:raise
 except Exception:time.sleep(2)
raise SystemExit('Service did not become ready: '+a.url)
