from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Image
from html import escape
ROOT=Path(__file__).resolve().parents[1]
pages=[
('口播精简：产品说明草稿','帮助已经录好中文单人口播的教程、知识或经验作者，在发布前确认必留信息，通过按句删减、恢复与对照，将长口播整理为目标时长内的短视频。\n具体场景：作者录制90–180秒的面试经验或教程，想做成60或90秒短版。他知道哪些条件和数字不能删，但不想反复拖动时间轴。\n核心任务：选择完整语义块，确认必留，检查删减与恢复，得到对应的真实视频。\n定位为VivaVideo口播任务的专项体验改进。剪映、CapCut与Descript已有文本剪辑能力，学习成熟交互，不宣称行业首创。\n公开依据：quvideo.com/zh/products；capcut.cn；capcut.com/resource/edit-video-with-text；descript.com/features。\n状态：HTTP、19组真实Chrome浏览器检查与实际服务重启验收通过；已有真实截图和连续操作录屏。本文仍因个人经历待补而保留草稿标识。'),
('使用流程与实际产物','开始 → 体验样例或导入MP4+SRT → 选择目标 → 确认最多5个必留块 → 查看建议并决定应用 → 逐块删减、恢复或撤销 → 生成实际MP4 → 播放并下载。\n工作台包含原片播放器、语义块与原片时间、必留状态、保留/删除、建议理由和预计时长。正式预览播放渲染产物。\n样例采用原创脚本、eSpeak NG普通中文合成旁白和示例文字卡；不是用户真实经历或真人口播。原片136.567秒，13块，推荐必留s03/s04/s05共35.267秒。\n实际导出：90秒目标产物77.988秒，60秒目标产物58.022秒，全部恢复136.588秒。既有三份产物保留；本轮另通过浏览器生成并下载77.988秒短片，核对MP4和SRT哈希。\nMP4不烧录字幕；SRT与VTT来自同一剪辑清单，视频与字幕单独下载。下图为本轮真实浏览器结果页截图。'),
('边界与产品判断','必留块由后端保护；删除前必须取消必留，锁定已删除块会同时恢复。必留超过目标时展示冲突，允许增加时长或重新确认必留。\n空选择不能生成。超目标需用户明确确认按当前时长导出。恢复后旧视频标记上一版，不能当当前结果下载。\n建议返回候选，应用前不覆盖选择。用户编辑后旧建议失效；渲染使用不可变快照，旧任务完成不覆盖新选择。失败保留编辑，可重试。\n选择完整句组，是为了减少句中截字风险；不代表语义绝对正确。目标是上限，无需恰好60秒。\n只保留一项：确认必留后，按文本删减与恢复，并导出真实对应的视频。\n主动舍弃：逐字改写合成原声、多人分离、专业时间线、自动发布、收费和训练模型。先做好可检查的完整任务。'),
('验证与真实经历待补','已执行：41项Python测试、9项前端状态与模板测试、前端构建。\n6秒工程样例逐帧检查：删中间后为A60+C60帧，B为零；频率440→880Hz；后段字幕前移2000ms；恢复后返回180帧。\n已检查：锁定、撤销、版本冲突、旧结果、会话归属、重启恢复、真实输出与记录同源。两处并发覆盖导出确认的竞态已复现并修复。\n本轮已执行：HTTP Range206/416与后缀/HEAD、Cookie浏览器隔离、原片/成片音视频解码和VTT、浏览器下载哈希、桌面/手机布局、上传错误、失败重试及服务重启。录屏采集真实桌面和浏览器声音，保留渲染等待。没有用户访谈或真人切口验证，人工逐字听审仍未完成。\n最可能失败：字幕不准切掉字头字尾；确认步骤比手剪慢；删整句仍影响上下文；作者已有工具足够好。\n用户最喜欢产品：尚待本人提供产品/功能、近期任务、有效设计及只改一处的真实经历。此项缺失，不能直接交卷。'),
('AI分工与运行交付','用户通过交接任务书确定口播精简方向、范围和真实交付要求。Codex辅助开发、测试、修复、文档；作者保留最终表达与提交判断。\n未调用文本模型；当前为规则建议。样例规则绑定视频和字幕哈希，新输入采用保守规则。无把握的条件、否定、数字留给作者复核。\n实际修正包括：修复音轨尾部封装不足、空选择统计异常、并发确认丢失；数字提示避免将“换一种”当数值。\n启动：在允许本地网络的终端，进入工程后运行bash scripts/run_demo.sh。默认127.0.0.1:8765，已占用则顺延；本轮实际地址127.0.0.1:8767。以启动终端输出为准。\n交付：README、VALIDATION.md、AI_USAGE.md、examples中的MP4/SRT/修改记录、源码。\n此前socket限制已解除。验收脚本修正回环请求误经代理的问题；缓存Chromium不支持MP4解码，使用临时目录Chrome完成实测。最终招聘平台交卷由用户执行。')]
# Keep the illustrated flow page concise enough for the five-page limit.
pages[1] = ('使用流程与实际产物', '样例或MP4+SRT导入 → 确认目标和必留 → 查看规则建议 → 人工删减、恢复或撤销 → 生成、播放并下载真实成片。\n原创合成样例136.567秒，13块；必留s03/s04/s05共35.267秒。实际保守建议116.833秒，需人工继续删减；本轮浏览器成片77.988秒。\n浏览器实际下载MP4、SRT和记录，哈希核对一致。字幕另附SRT，预览采用VTT。下图是真实Chrome结果页；其他截图和验收记录见本地deliverables。')
md='# 产品说明草稿\n\n'+'\n\n'.join('## '+a+'\n\n'+b.replace('\n','\n\n') for a,b in pages)
(ROOT/'deliverables/product_brief.md').write_text(md)
pdfmetrics.registerFont(TTFont('CN','/usr/share/fonts/truetype/noto/SIMSUN.TTC',subfontIndex=0))
pdfmetrics.registerFont(TTFont('Head','/usr/share/fonts/truetype/noto/SIMHEI.TTF'))
body=ParagraphStyle('body',fontName='CN',fontSize=12,leading=21,spaceAfter=15,wordWrap='CJK')
head=ParagraphStyle('head',fontName='Head',fontSize=22,leading=30,spaceAfter=24)
story=[]
for i,(title,text) in enumerate(pages):
 if i:story.append(PageBreak())
 story.append(Paragraph(escape(title),head))
 for p in text.split('\n'):story.append(Paragraph(escape(p),body))
 if i == 1 and (ROOT/'deliverables/browser_result.png').is_file():
  img=Image(str(ROOT/'deliverables/browser_result.png'))
  img.drawHeight=450*img.imageHeight/img.imageWidth;img.drawWidth=450
  story.append(img)
def footer(c,d):
 c.setFont('CN',9);c.drawString(44,25,'口播精简｜验收通过，个人经历待补的材料草稿');c.drawRightString(A4[0]-44,25,str(d.page))
SimpleDocTemplate(str(ROOT/'deliverables/product_brief.pdf'),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=45,bottomMargin=45).build(story,onFirstPage=footer,onLaterPages=footer)
print('product_brief.pdf generated')
