"""Build offline HTML, illustrated PDF and an exactly five-page executive brief."""
from pathlib import Path
from html import escape
import base64
import mimetypes
import re
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib import colors

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables/v2'
pdfmetrics.registerFont(TTFont('CN','/usr/share/fonts/truetype/noto/SIMSUN.TTC',subfontIndex=0))
pdfmetrics.registerFont(TTFont('Head','/usr/share/fonts/truetype/noto/SIMHEI.TTF'))
body=ParagraphStyle('body',fontName='CN',fontSize=10.5,leading=17,spaceAfter=9,wordWrap='CJK')
small=ParagraphStyle('small',parent=body,fontSize=8,leading=12,textColor=colors.HexColor('#526875'))
heads={i:ParagraphStyle('h%d'%i,fontName='Head',fontSize={1:23,2:17,3:13}[i],leading={1:30,2:23,3:19}[i],spaceBefore=14,spaceAfter=12,wordWrap='CJK') for i in [1,2,3]}

def inline(text, html=False):
 text=escape(text)
 text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:('<a href="'+m[2]+'">'+m[1]+'</a>'),text)
 text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
 text=re.sub(r'`([^`]+)`',r'<b>\1</b>',text)
 return text

def picture(relative,label):
 path=OUT/relative
 if not path.is_file():raise RuntimeError('Missing genuine screenshot: '+str(path))
 img=Image(str(path));scale=min(480/img.imageWidth,310/img.imageHeight)
 img.drawWidth=img.imageWidth*scale;img.drawHeight=img.imageHeight*scale
 return [img,Spacer(1,5),Paragraph(escape(label),small),Spacer(1,12)]

def footer(c,d):
 c.setFont('CN',8);c.drawString(40,24,'口播精简 V2｜实际实现、公开竞品资料与验证记录');c.drawRightString(A4[0]-40,24,str(d.page))

def build():
 text=(OUT/'PRODUCT_REPORT.md').read_text();lines=text.splitlines();story=[];html=[];i=0
 while i<len(lines):
  line=lines[i].strip();i+=1
  if not line:continue
  if line.startswith('|'):
   rows=[line]
   while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
   cells=[[x.strip() for x in row.strip('|').split('|')] for row in rows if not re.match(r'^\|[\s|:-]+\|$',row)]
   n=len(cells[0]);table=Table([[Paragraph(inline(c),small) for c in row]for row in cells],colWidths=[(A4[0]-80)/n]*n,repeatRows=1,hAlign='LEFT')
   table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4f3ef')),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#d9e3e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
   story+=[table,Spacer(1,14)]
   html.append('<div class="table-scroll"><table>'+''.join('<tr>'+''.join('<'+('th'if k==0 else'td')+'>'+inline(c,True)+'</'+('th'if k==0 else'td')+'>'for c in row)+'</tr>'for k,row in enumerate(cells))+'</table></div>');continue
  match=re.match(r'!\[([^\]]*)\]\(([^)]+)\)',line)
  if match:
   label,relative=match.groups();story+=picture(relative,label);p=OUT/relative
   data=base64.b64encode(p.read_bytes()).decode();mime=mimetypes.guess_type(p.name)[0]or'image/png'
   html.append('<figure><img loading="lazy" src="data:'+mime+';base64,'+data+'" alt="'+escape(label)+'"/><figcaption>'+escape(label)+'</figcaption></figure>');continue
  match=re.match(r'^(#{1,3}) (.*)',line)
  if match:
   level=len(match[1]);story.append(Paragraph(inline(match[2]),heads[level]));html.append('<h%d>%s</h%d>'%(level,inline(match[2]),level));continue
  if line.startswith('- '):line='• '+line[2:]
  story.append(Paragraph(inline(line),body));html.append('<p>'+inline(line,True)+'</p>')
 SimpleDocTemplate(str(OUT/'PRODUCT_REPORT.pdf'),pagesize=A4,leftMargin=40,rightMargin=40,topMargin=38,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
 css='body{margin:0;background:#f2f6f5;color:#18343e;font:16px/1.85 system-ui,"Noto Sans CJK SC",sans-serif}main{max-width:1020px;margin:40px auto;background:white;padding:48px;border-radius:16px}h1{font-size:30px}h2{border-top:1px solid #dbe6e2;padding-top:26px;margin-top:38px}h3{color:#087e77}a{color:#087e77}figure{margin:24px 0;padding:18px;border:1px solid #dbe6e2;border-radius:10px}img{display:block;max-width:100%;max-height:850px;margin:auto}figcaption{font-size:13px;color:#5b7179;margin-top:12px}table{border-collapse:collapse;min-width:700px;width:100%}td,th{border:1px solid #dbe6e2;padding:12px;text-align:left;font-size:14px}th{background:#e4f3ef}.table-scroll{overflow:auto}@media(max-width:700px){main{padding:20px;margin:0;border-radius:0}}'
 (OUT/'PRODUCT_REPORT.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>口播精简 V2 产品报告</title><style>'+css+'</style><main>'+''.join(html)+'</main></html>')
 chapters=[
 ('1｜目标、用户与定位',[
  '帮助中文教程、知识与经验分享作者，把90–180秒的已有口播整理成目标时长内的真实短片。核心控制点是：重要信息保留、修改可解释、随时可恢复、导出与选择一致。',
  '用户与市场定位来自任务书和待验证假设。当前没有访谈、提效百分比或营收结论；应测量完整任务耗时、合格导出、纠错量、建议采纳和再次使用意愿。',
  '定位为VivaVideo口播流程的专项概念演示，处于素材导入之后、包装发布之前。文本剪辑已成熟，本轮聚焦可检查的任务衔接。']),
 ('2｜旧版缺口与V2流程',[
  '旧版需要MP4+SRT，以整句删除/恢复为主，提供规则建议和实际导出。人工验收要求补上自动字幕、精修、声音修改、逐项建议、背景音处理及真人样例。',
  'V2流程：导入视频 → 本机生成字幕 → 校对/备注 → 剪词与整句重排 → 逐项确认建议 → 人工补录 → 真实预览与交接下载。',
  '文字校对只改字幕；删除词语会同步剪音视频；新说法需要对应补录。界面明确区分三种结果。']),
 ('3｜竞品比较与设计取舍',[
  'VivaVideo官方产品页介绍自动字幕、AI配音及多轨能力，提示本模块应复用宿主工程和字幕轨。CapCut官方教程展示文本关联媒体删除和恢复，提示编辑结果应直接可见。',
  'Descript官方文档分别说明删除/移动媒体、校对和备注，我们沿用这种操作区分。Premiere将文本粗剪衔接专业时间线，并提示依据最终序列生成字幕；本Demo统一剪辑清单后导出MP4/SRT/VTT。',
  '完整报告附官方页面或界面示例，来源与实测范围分开。未登录付费产品实测，未把CapCut海外能力自动外推到所有剪映版本。']),
 ('4｜实际技术链路与验收',[
  '本机faster-whisper medium CPU int8生成中文与词时间戳；Demucs分离人声/背景；Qwen2.5-7B Q4_K_M生成方针和具体建议。长任务后台执行，失败保留编辑。',
  '词切点量化到30fps；模型不输出媒体命令，必留、ID、时间和版本由代码验证。补录保持原段时长，过长拒绝、过短补静音；不做口型同步。',
  '真人样例来自Wikitongues，CC BY-SA 4.0，署名与变更记录保留。方言与专名存在识别错误，提供实际校对案例；纯器乐不生成伪口播。完整验收记录以随附JSON为准。']),
 ('5｜不足、下一步与交付',[
  '主要不足：口音/专名识别、帧级切口、校对后继续剪词的交互、补录口型不一致，以及CPU时延。分离也不能保证排除歌曲人声或重叠说话。',
  '下一阶段：作者校正稿强制对齐、切口微调与前后试听、更多真人补录/BGM验收；有明确声源授权后再验证同声线合成，宿主确定后接原生工程与发布流程。',
  '交付：完整图文报告、五页摘要、旧版基线、V2截图与真实录屏、真人来源、MP4/SRT/编辑记录/交接包、源码和复现说明。代码与轻量证据同步指定GitHub；模型及大媒体留在本地交付包。'])]
 brief=[]
 for index,(title,paras)in enumerate(chapters):
  if index:brief.append(PageBreak())
  brief.append(Paragraph(title,heads[1]))
  for para in paras:brief.append(Paragraph(escape(para),body))
  if index==1:brief+=picture('acceptance/02_real_editor.png','V2真实浏览器界面；完整截图见产品报告。')
  if index==3:brief.append(Paragraph('本轮自动验收：'+str(len(json.loads((OUT/'acceptance/browser_validation.json').read_text())['passed']))+'组真实浏览器检查；具体耗时、版本、下载哈希与推理来源见记录。',body))
 SimpleDocTemplate(str(OUT/'EXECUTIVE_BRIEF.pdf'),pagesize=A4,leftMargin=40,rightMargin=40,topMargin=38,bottomMargin=42).build(brief,onFirstPage=footer,onLaterPages=footer)
 (OUT/'EXECUTIVE_BRIEF.md').write_text('# 口播精简 V2 五页摘要\n\n'+'\n\n'.join('## '+t+'\n\n'+'\n\n'.join(ps)for t,ps in chapters))
 print('Built illustrated PDF, offline HTML and five-page brief')

if __name__=='__main__':build()
