"""Explicit allowlist of shareable delivery artifacts, never the private data directory."""
from functools import lru_cache
from html import escape
from .config import ROOT
from .media import sha256_file

FILES={
 'optimization':('本轮审阅优化说明','optimization/REVIEW_RESPONSE.md','text/plain; charset=utf-8'),
 'showcase':('AI精简前后对比','optimization/SHOWCASE.md','text/plain; charset=utf-8'),
 'before':('真人原片（CC BY-SA 4.0）','optimization/showcase_before.mp4','video/mp4'),
 'after':('AI精简成片（CC BY-SA 4.0）','optimization/showcase_after.mp4','video/mp4'),
 'captions':('AI精简成片字幕','optimization/showcase_after.srt','application/x-subrip'),
 'report':('V2基线图文报告 PDF','v2/PRODUCT_REPORT.pdf','application/pdf'),
 'html':('V2基线离线图文报告 HTML','v2/PRODUCT_REPORT.html','text/html; charset=utf-8'),
 'brief':('五页摘要','v2/EXECUTIVE_BRIEF.pdf','application/pdf'),
 'current-recording':('本轮真实对比与切口试听录屏','optimization/walkthrough.mp4','video/mp4'),
 'recording':('V2基线连续操作录屏','v2/walkthrough.mp4','video/mp4'),
 'evidence':('证据索引与哈希','optimization/EVIDENCE_INDEX.json','application/json'),
 'validation':('真实模型评分与候选记录','optimization/showcase_validation.json','application/json'),
 'edit-record':('实际渲染编辑记录','optimization/showcase_record.json','application/json'),
 'guide':('本轮验收步骤','optimization/ACCEPTANCE_GUIDE.md','text/plain; charset=utf-8'),
 'package':('完整本地交付包','optimization/delivery.zip','application/zip'),
}

@lru_cache(maxsize=32)
def _digest(path,modified,size):return sha256_file(path)

def index():
 result=[]
 for key,(label,relative,mime) in FILES.items():
  path=ROOT/'deliverables'/relative
  if not path.is_file():continue
  stat=path.stat()
  result.append({'id':key,'title':label,'filename':path.name,'mimeType':mime,'bytes':stat.st_size,
                 'sha256':_digest(path,stat.st_mtime_ns,stat.st_size),'url':'/api/deliverables/'+key})
 return result

def page():
 entries=index()
 rows=''.join('<tr><td><a href="'+e['url']+'">'+escape(e['title'])+'</a></td><td>'+escape(e['filename'])+'</td><td>%.1f MB</td><td><code>'%(e['bytes']/1024/1024)+e['sha256']+'</code></td></tr>' for e in entries)
 return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>口播精简交付中心</title><style>body{font:15px/1.7 system-ui;background:#f5f7f8;color:#173344;margin:32px}main{max-width:1100px;margin:auto}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;border:1px solid #dce5e5;text-align:left}code{word-break:break-all;font-size:11px}a{color:#07675f}.table{overflow:auto}.compare{display:grid;grid-template-columns:1fr 1fr;gap:20px}.compare video{width:100%;background:#152b30}figure{margin:0}h2{margin-top:30px}@media(max-width:650px){.compare{grid-template-columns:1fr}body{margin:16px}}</style><main><a href="/">返回工作台</a><h1>报告、对比视频与验收材料</h1><p>文件由当前服务器直接提供，可通过相同SSH端口转发下载。真人素材署名及CC BY-SA 4.0许可见对应报告；成片体现一次特定编辑任务，不代表普遍准确率或真人听审结论。</p><h2>AI任务粗剪：128.2秒 → 25.2秒</h2><p>任务：一分钟内的个人语言背景简介。AI整组省略家庭工作、书店活动和邀约，保留开场、出生、迁居、结束语。字幕仍待人工校对。</p><div class="compare"><figure><video controls preload="metadata" src="/api/deliverables/before"></video><figcaption>原片 · 128.2秒</figcaption></figure><figure><video controls preload="metadata" src="/api/deliverables/after"></video><figcaption>真实模型建议全部接受 · 25.2秒 · 缩短80.35%</figcaption></figure></div><h2>下载与核对</h2><div class="table"><table><tr><th>内容</th><th>文件</th><th>大小</th><th>SHA256</th></tr>'''+rows+'''</table></div><p>此入口仅在本地工作台模式开放，文件列表固定，不开放私人项目数据目录。</p></main></html>'''
