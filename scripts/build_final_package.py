"""Build the offline reviewer package from explicitly selected, public artifacts."""
from pathlib import Path
from html import escape
import json,hashlib,zipfile,subprocess,shutil,re
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'deliverables/final_submission'
STEPS=[
 ('01-entry.png','1 进入任务','选择已获授权的真人样例；目标是将已有口播整理成一分钟内简介。'),
 ('02-locked-conflict.png','2 保护必留内容','目标短于必留内容时提示冲突并禁用生成，不自动删除保护内容。'),
 ('03-transcript.png','3 文稿与原片联动','核对主线、目标和句子，点击文字定位；可剪词、恢复和整句调整。'),
 ('04-real-suggestions.png','4 审核真实模型候选','本次Qwen实际推理148.2秒产生32项候选；作者可逐项接受、拒绝或批量确认。'),
 ('05-sentence-recording.png','5 为一句补录声音','上传或直接录音，先试听再识别和确认；图中使用授权样例测试输入，每句上限60秒。'),
 ('06-failure-retry.png','6 失败后可继续','浏览器中断一次渲染请求，界面保留编辑并提供重试；服务端故障注入关闭。'),
 ('07-result.png','7 播放和下载结果','本轮确认及手动恢复后导出27.588秒短片；切口可循环试听，MP4/SRT/记录同版下载。'),
 ('08-stale-result.png','8 继续编辑与版本保护','编辑后旧成片标注为上一版，保留预览并禁用当前下载，提示重新生成。'),
]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def flow():
 from reportlab.pdfgen import canvas
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 from reportlab.lib.utils import ImageReader
 from reportlab.lib.colors import HexColor
 from reportlab.lib.styles import ParagraphStyle
 from reportlab.platypus import Paragraph
 pdfmetrics.registerFont(TTFont('FinalCN','/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'))
 pdfmetrics.registerFont(TTFont('FinalLatin','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
 def mixed(t):return ''.join('<font name="FinalLatin">'+escape(x)+'</font>' if x and ord(x[0])<256 else escape(x) for x in re.split(r'([\x00-\xff]+)',t))
 c=canvas.Canvas(str(OUT/'DEMO_FLOW.pdf'),pagesize=(960,750));c.setTitle('口播精简｜同版本八图流程')
 style=ParagraphStyle('caption',fontName='FinalCN',fontSize=13,leading=22,wordWrap='CJK')
 md=['# 同版本八图流程','应用核心固定于fce60bf；全部为该版本真实页面。第2、6、8张在录屏后重新复现，确保错误反馈和视频预览清晰可读，不声称全部为视频截帧。']
 figures=[]
 for i,(name,title,description) in enumerate(STEPS):
  c.setFillColor(HexColor('#143d43'));head=Paragraph(mixed(title),ParagraphStyle('head',fontName='FinalCN',fontSize=23,leading=28));head.wrap(896,40);head.drawOn(c,32,705)
  para=Paragraph(mixed(description),style);_,h=para.wrap(896,80);para.drawOn(c,32,685-h)
  p=OUT/'screenshots'/name;im=ImageReader(str(p));w,height=im.getSize();scale=min(896/w,535/height);dw,dh=w*scale,height*scale
  c.drawImage(im,(960-dw)/2,82+(535-dh)/2,dw,dh,preserveAspectRatio=True)
  c.setFillColor(HexColor('#526875'));foot=Paragraph(mixed('同版本实际截图｜Wikitongues, Teddy Nee · CC BY-SA 4.0｜测试输入与真实模型分别披露'),ParagraphStyle('foot',fontName='FinalCN',fontSize=9,leading=12));foot.wrap(860,20);foot.drawOn(c,32,40);c.setFont('FinalLatin',10);c.drawRightString(928,42,str(i+1));c.showPage()
  md.extend(['','## '+title,description,'','!['+title+'](screenshots/'+name+')'])
  figures.append('<section><h2>'+escape(title)+'</h2><p>'+escape(description)+'</p><img loading="lazy" src="screenshots/'+name+'" alt="'+escape(title)+'"></section>')
 c.save();(OUT/'DEMO_FLOW.md').write_text('\n'.join(md)+'\n')
 (OUT/'START_HERE.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>口播精简｜最终交付</title><style>body{font:16px/1.8 system-ui;background:#f4f7f7;color:#163842;margin:24px}main{max-width:1080px;margin:auto}a{color:#07675f}section{background:white;padding:24px;margin:24px 0;border-radius:12px}img,video{width:100%;height:auto}nav{display:flex;gap:20px;flex-wrap:wrap}.hint{color:#526875}</style><main><h1>口播精简｜最终交付</h1><p>将已有中文口播整理成可审阅、可恢复的短片。</p><nav><a href="product_brief_5pages.pdf">五页产品说明 PDF</a><a href="ai_usage_record.pdf">AI 使用记录 PDF</a><a href="DEMO_FLOW.pdf">八图流程 PDF</a><a href="README.md">交付说明</a></nav><section><h2>实际操作 Demo · 2 分 51.56 秒</h2><video controls preload="metadata" src="demo_walkthrough.mp4"></video><p class="hint">连续实际屏幕和浏览器声音；真实模型推理148.2秒在录制前完成并明示。测试麦克风不是本人真人新录；网络失败由浏览器中断请求演示。</p></section><section><h2>本轮实际导出 · 27.588 秒</h2><video controls preload="metadata" src="demo_result.mp4"></video><p><a href="demo_result.srt">同步字幕 SRT</a> · <a href="demo_edit_record.json">编辑记录</a> · <a href="ATTRIBUTION.md">来源与许可</a></p><p class="hint">这是有接受/拒绝及手动恢复的任务粗剪。专名字幕与切口仍需作者听审；不与历史25.188秒AI全接受示例混用。</p></section>'''+''.join(figures)+'''<p>媒体：Wikitongues, Teddy Nee，CC BY-SA 4.0；转码、截取及剪辑。个人观点按用户审阅稿保留，提交前由本人核对。</p></main></html>''')
def manifest_and_zip():
 exclude={'submission_package.zip','MANIFEST.json','PUBLIC_ACCESS.json'}
 paths=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in exclude and not p.name.startswith('.'))
 records=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths]
 (OUT/'MANIFEST.json').write_text(json.dumps({'applicationCommit':'fce60bfcbaf96a4b2574bc6b582753d0561f4424','documentsSourceCommit':'cd063651edf49767dbd15f9fbd7a51446f379c63','note':'Manifest excludes itself, package ZIP and post-publication access receipt to avoid circular hashes. No private data, cookies, credentials or model weights.','files':records},ensure_ascii=False,indent=2)+'\n')
 with zipfile.ZipFile(OUT/'submission_package.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in paths+[OUT/'MANIFEST.json']:z.write(p,p.relative_to(OUT))
 with zipfile.ZipFile(OUT/'submission_package.zip') as z:assert z.testzip() is None
 print('Package bytes:',(OUT/'submission_package.zip').stat().st_size,'SHA256:',sha(OUT/'submission_package.zip'))
if __name__=='__main__':
 flow();manifest_and_zip()
