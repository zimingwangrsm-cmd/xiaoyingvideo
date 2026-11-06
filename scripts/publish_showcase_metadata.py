"""Build a traceable comparison summary from an actual local-model render receipt."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'deliverables/optimization';r=json.loads((p/'showcase_validation.json').read_text())
kept='\n'.join('- '+b['id']+'：'+b['originalAsrText'] for b in r['kept'])
(p/'SHOWCASE.md').write_text('''# 真实AI精简示例：语言背景简介

本例为任务导向粗剪：把包含语言背景、家庭成员工作、书店活动与邀约的完整分享，整理成一分钟以内的语言背景简介。

| 指标 | 实测结果 |
|---|---|
| 真人原片 | %.3f秒 |
| 成片 | %.3f秒 |
| 时长减少 | %.2f%% |
| 保留内容 | %d个完整片段 |
| 操作来源 | 本地Qwen评估相关性＋实际帧预算选择；全部接受候选，没有人工追加删除 |
| 模型耗时 | %.1f秒（CPU，包含结构化评分与前后依赖判断） |

## 明确的编辑目标

%s

这是演示者给定的编辑任务，不是模型自动证明了“哪些话没有价值”。家庭和书店内容是本任务中的支线；同一素材换一个主线可能得到不同选择。目标是上限，不强行凑满60秒。

## 保留内容对照

%s

以上为自动识别文字，仍有专名和口音误识别，例如人名需要本人确认。文本层已检查“开场／语言、出生地、迁居、结束语”的顺序；未声称作者已盲听同意或已完成专业字幕审校。

## 如何查看

在运行中的Demo打开 `/delivery`，可以直接下载原片、成片和SRT；默认首页的Tao样例提供相同任务预设，可重新生成实际AI建议。

- 原片：showcase_before.mp4
- 成片：showcase_after.mp4
- 字幕：showcase_after.srt
- 编辑记录：showcase_record.json
- 全部候选、评分与前后对比：showcase_validation.json

## 来源与许可

%s，%s。源视频：%s

样例与剪辑媒体沿用CC BY-SA 4.0，已作转码、截取及按句删减；未改变原声内容，未使用同声线生成，未声称原作者为Demo背书。
'''%(r['sourceDurationMs']/1000,r['actualDurationMs']/1000,r['reductionPercent'],len(r['kept']),r['llmSeconds'],r['brief'],kept,r['author'],r['license'],r['sourceUrl']),encoding='utf-8')
print('SHOWCASE.md generated')
