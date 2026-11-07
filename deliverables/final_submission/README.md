# 口播精简｜最终交付

交付内容已完成。建议向评审提交下面三项，或直接提交完整ZIP；不用提供localhost地址，不需要启动模型。

1. [五页产品说明 PDF](product_brief_5pages.pdf)（[可编辑 DOCX](product_brief_5pages.docx)）。个人视角和观点沿用用户审阅稿，提交前由本人核对。
2. [实际操作视频 MP4](demo_walkthrough.mp4)：**2分51.56秒**，应用核心固定于[fce60bf](https://github.com/zimingwangrsm-cmd/xiaoyingvideo/commit/fce60bfcbaf96a4b2574bc6b582753d0561f4424)。亦可使用[八图流程 PDF](DEMO_FLOW.pdf)。
3. [AI使用记录 PDF](ai_usage_record.pdf)（[可编辑 DOCX](ai_usage_record.docx)）。开发助手、产品模型与人的判断分别说明。

[下载完整提交包](https://codeload.github.com/zimingwangrsm-cmd/xiaoyingvideo/zip/refs/heads/delivery-final-20261107-fce60bf)。GitHub归档解压后进入顶层文件夹，打开START_HERE.html即可离线阅读、播放和浏览八图流程；视频也可直接用播放器打开。GitHub中选择Raw/Download下载原文件，无需仓库协作者权限。

## 本轮Demo说明

- 视频连续采集真实桌面和浏览器播放声音，没有拼接静态图、倍速或替换配音。
- 实际本地Qwen在录屏前推理148.2秒，生成32项建议，录屏从审核阶段开始；画面与记录均披露等待范围。
- 演示逐项接受/拒绝、剩余建议确认、手动删句/撤销、补录、恢复原声、网络失败重试、实际生成和下载，以及继续编辑后旧成片禁用下载。
- 补录使用授权样例测试麦克风输入，真实执行MediaRecorder、WAV、ASR和确认接口；不冒充本人真人新录或作者听审。
- [本轮实际导出](demo_result.mp4)为27.588秒、6段；[SRT](demo_result.srt)与[编辑记录](demo_edit_record.json)对应同一快照。历史25.188秒示例是另一轮全接受结果，不混算。
- 第2、6、8张截图在同一应用版本下重新复现，使错误反馈和已解码的预览清晰可读；其他截图来自准备及录制过程。

## 复核与边界

[最终验证报告](FINAL_VALIDATION.md) · [文件哈希清单](MANIFEST.json) · [素材署名与许可](ATTRIBUTION.md) · [个人措辞保留记录](WORDING_REVIEW.md)。

67项后端、16项前端检查通过；真实模型、分钟录音、浏览器回归、视频播放和下载分开记载。物理手机/麦克风、作者音质听审与专名字幕真值未被自动化替代。应用未作为公开Web服务部署；公开交付的是文件附件。本人完成最终措辞核对和招聘平台提交。

开发者本机入口仍为8767，`/delivery`提供同一批附件；这只是本地领取方式，不是评审访问地址。

[公开下载核验回执](https://github.com/zimingwangrsm-cmd/xiaoyingvideo/blob/main/deliverables/final_submission/PUBLIC_ACCESS.json)在文件发布后单独提供；不进入ZIP以避免循环校验。
