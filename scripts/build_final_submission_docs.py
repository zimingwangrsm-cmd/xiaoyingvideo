"""Finalize the supplied DOCX template while preserving the user's personal paragraphs."""
from pathlib import Path
import json,re,shutil
from docx import Document
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'deliverables/submission_draft';OUT=ROOT/'deliverables/final_submission'
CODE='fce60bfcbaf96a4b2574bc6b582753d0561f4424'

def replace_paragraph(p,text):
    if p.runs:
        p.runs[0].text=text
        for run in p.runs[1:]:run.text=''
    else:p.add_run(text)

def main():
    doc=Document(SOURCE/'product_brief_5pages.docx');original=[p.text for p in doc.paragraphs]
    updates={
      1:'交付版｜产品说明五页｜2026 年 11 月 7 日｜个人表述请本人提交前确认',
      11:'材料依据：用户审阅交接稿与当前仓库。最终应用整合538fa8e兼容性修复，固定于fce60bf；本机真实浏览器、录音与导出证据另附。历史失败与原版结果保留为审阅依据，不混算为当前验收。',
      24:'样例进入 → 明确主线与必留 → 审核真实模型候选 → 接受或拒绝 → 试听补录 → 生成、播放与下载。本次连续录屏从候选审核阶段开始，真实模型推理已提前完成，耗时在画面中明示。',
      43:'历史AI任务示例：给定“一分钟以内的个人语言背景简介”，保留开场、出生、迁居与结束语，整组省略家庭工作、书店活动和邀约。原片128.200秒转为25.188秒，保留5段、减少80.35%；该轮全部接受候选，没有额外人工删除。',
      44:'该历史示例由本地Qwen评估相关性，CPU推理199.9秒。它是一个特定任务的结果，不代表普遍压缩比例或作者质量认可。最终Demo另在当前版本重新推理，并演示接受、拒绝和手工恢复，不能把两轮结果混为同一次实验。',
      46:'最终交付整合恒定帧率与依赖兼容修复，交付机独立依赖环境67项后端、16项前端检查通过。当前版本重新验证真实模型、浏览器补录、60秒自动停止、长补录延长末帧、字幕顺延和MP4下载。测试麦克风为授权样例输入，手机为尺寸模拟；实机与人工听审未被这些结果替代。',
      47:'本次Demo交付',
      48:'附件包含2–3分钟同版本实际操作视频及8张截图流程，展示用户确认、补录、网络失败重试、真实导出与旧版本保护。模型推理在录屏前真实完成并明示耗时；录屏内操作连续。提交附件或公开仓库文件，网页回环地址仅供开发者验收，不作为评审入口。',
      51:'源码与交付附件：github.com/zimingwangrsm-cmd/xiaoyingvideo。入口为deliverables/final_submission/README.md；环境、验证与文件哈希分别见FINAL_VALIDATION.md和MANIFEST.json。',
      63:'Whisper、Qwen和Demucs分别负责字幕、建议与声音分离，AI使用记录另附。Codex已完成最终技术验收、录屏和交付整理；最终个人表述核对与招聘平台提交由我本人完成。',
    }
    for index,text in updates.items():replace_paragraph(doc.paragraphs[index],text)
    for index in [55,57,58,60,62]:assert doc.paragraphs[index].text==original[index], 'Personal wording must remain unchanged'
    doc.save(OUT/'product_brief_5pages.docx')
    # Use the supplied Markdown as the textual companion; replace only the corresponding technical paragraphs.
    md=(SOURCE/'PRODUCT_BRIEF_DRAFT.md').read_text()
    for index,text in updates.items():
        if original[index] in md:md=md.replace(original[index],text)
    md=md.replace('### Demo 提交方案','### 本次Demo交付')
    (OUT/'PRODUCT_BRIEF.md').write_text(md)
    usage=Document(SOURCE/'ai_usage_record.docx')
    for p in usage.paragraphs:
        if p.text.startswith('非最终提交草稿'):
            replace_paragraph(p,'交付版｜2026 年 11 月 7 日｜本人使用方式与观点按审阅稿保留，提交前由本人确认。开发助手、运行模型与自动化证据分别记录。')
    usage.add_heading('最终交付补充',level=2)
    extra='本轮Codex核对文档分支与538fa8e修复，在交付机独立依赖环境通过67项后端、16项前端检查，并重新运行真实本地Qwen、浏览器补录与视频导出。最终连续录屏使用真实预先生成的候选，明示推理耗时；麦克风为授权测试音频输入，网络失败由浏览器中断一次请求演示。不把这些操作归为本人亲自逐项测试，也不把自动化结果写成人工音质认可。'
    usage.add_paragraph(extra);usage.save(OUT/'ai_usage_record.docx')
    ai=(SOURCE/'AI_USAGE_DRAFT.md').read_text();ai=re.sub(r'非最终提交草稿[^\n]+','交付版｜2026年11月7日｜个人使用视角按审阅稿保留；提交前由本人核对。',ai,count=1)
    (OUT/'AI_USAGE.md').write_text(ai+'\n## 最终交付补充\n\n'+extra+'\n')
    (OUT/'WORDING_REVIEW.md').write_text('''# 文字核对记录\n\n个人体验与观点沿用文档分支cd063651，不新增项目、日期、收益数字、故障故事或Claude Code代码贡献。五页DOCX第5页五段核心个人表述逐段比较一致。更新仅涉及实际完成的兼容性修复、验证、Demo附件及交付状态；提交前本人核对个人表述的责任保留。\n\n原交接稿已随仓库归档在submission_draft，应用未从该文档分支回退。\n''')
    print('Updated supplied DOCX templates; personal paragraphs preserved')
if __name__=='__main__':main()
