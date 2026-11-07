# 口播精简｜小影产品概念 Demo

本地口播编辑 Demo：自动字幕、文字校对、按词/按句剪辑、必留保护、本地模型建议和真实 MP4 导出。当前为 **2026-11-07 最终交付版**。应用核心固定于 `fce60bf`，整合兼容性修复并完成本机复验。

## 公网完整Demo

**[打开可直接使用的网页版](https://con-chip-variable-sleeping.trycloudflare.com)**：支持视频上传、真实字幕/建议模型、直接录音、人声分离及MP4导出，无需SSH转发。已部署为常驻服务并完成公网端到端验收；[部署详情](deliverables/deployment/README.md)。当前是临时HTTPS域名，隧道重建时会变更；固定域名可另行绑定。

## 最终交付入口

[最终材料与下载](deliverables/final_submission/README.md)：五页产品说明PDF/DOCX、AI使用记录、171.56秒实际操作视频、八图流程和完整ZIP。评审可直接下载附件或离线阅读，无需访问localhost或安装模型。技术验收见[FINAL_VALIDATION](deliverables/final_submission/FINAL_VALIDATION.md)。

## 2026-11-07 交互更新

每句话新增“补录这句”，可直接麦克风录音或上传，试听后提交识别并确认替换；每句补录上限已放宽到60秒，较长录音延长原句末帧。建议移到右侧“文稿 / AI建议”面板，内部滚动与状态筛选，左侧保持预览。入口仍是8767，刷新即可加载。[操作与验收记录](deliverables/recording_layout/RELEASE.md)。该布局版本16项前端检查及10组浏览器验收通过；[60秒补录更新与验证](deliverables/minute_recording/RELEASE.md)，实机麦克风仍需使用者授权测试。

## 使用与验收

已准备的服务器入口：`http://127.0.0.1:8767`。在自己电脑的终端运行：

```bash
ssh -N -L 8767:127.0.0.1:8767 <用户名>@<服务器地址>
```

浏览器打开 `http://localhost:8767`。只转发 Web 端口，无需转发模型的8781端口。

- 直接看效果：打开 `http://localhost:8767/delivery`，对比 **128.2秒 → 25.2秒** 的真人原片和AI任务粗剪，下载报告与交付包。
- 亲自操作：选择“AI精简示例：语言背景一分钟简介”，检查可编辑的主线和两段必留，再生成建议、确认、导出。CPU模型本例耗时约200秒；不同输入与负载会变化。
- 示例保留开场、出生地、迁居与结束语，整组省略家庭工作、书店活动与邀约。它是任务导向粗剪；字幕专名仍待人工校对，不代表方言识别准确率或作者听审结论。

[本轮验收步骤](deliverables/optimization/ACCEPTANCE_GUIDE.md) · [审阅逐项响应](deliverables/optimization/REVIEW_RESPONSE.md) · [真实模型结果](deliverables/optimization/SHOWCASE.md) · [需求范围表](deliverables/optimization/REQUIREMENTS_TRACE.md)

## 启动与复现

已有模型与素材时不要重新生成。本机最终Web环境为data/final_runtime，先激活该环境；全新环境按requirements-dev.txt安装。启动两个终端：

```bash
bash scripts/run_local_model.sh
# 另一个终端：
source data/final_runtime/bin/activate
DATA_DIR=data/acceptance_20261106 PORT=8767 bash scripts/run_v2.sh
```

首次安装、锁定模型版本及依赖见 [README_V2.md](README_V2.md)。只体验已备样例、手工剪辑与规则建议，可用 `PORT=8767 bash scripts/run_demo.sh`，无需启动本地模型。启动端口冲突时以终端实际输出为准；同一数据目录只运行一个服务。

```bash
python -m pytest tests -q
cd frontend
npm run check
npm run build
```

本轮实测：**67项后端、16项前端检查通过**；桌面草稿/失败/迟到响应/跨项目/键盘、多项建议以及手机尺寸完整任务通过。真实Qwen推理记录与确定性交互fixture分别存档，不混算。浏览器任务是Chromium模拟，未替代实机软键盘和人工听审。完整证据见 [最终交付索引](deliverables/final_submission/MANIFEST.json)。另在规则模式重跑21组旧浏览器流程通过。历史V2录屏/57项测试结论只对应其原版本。

## 数据和交付

服务只监听回环，使用匿名会话隔离。`APP_MODE=public`禁用视频与补录上传，不等于完成公网部署加固。私人状态、模型、缓存不提交Git；本地 `/delivery` 只开放固定白名单报告和公开授权媒体，不开放data目录。

GitHub提供源码、文字报告、验证JSON与检查过的截图；大视频/PDF/离线HTML/ZIP通过同一SSH端口的交付中心下载，当前没有公网下载站点。[数据许可及交接边界](deliverables/optimization/DATA_AND_INTEGRATION.md) · [人工质量评估协议](deliverables/optimization/QUALITY_PROTOCOL.md)

人工补录是同声线生成的替代范围；原生剪辑工程集成、真人新录补录听审、真实用户研究尚未完成。Wikitongues真人媒体及剪辑衍生内容为CC BY-SA 4.0，须保留署名和许可。

历史材料：[V1运行记录](deliverables/history/README_V1.md)、[V2基线产品报告](deliverables/v2/PRODUCT_REPORT.md)、[原独立审阅](deliverables/review/INDEPENDENT_REVIEW_2026-11-06.md)。历史数据不覆盖本轮结论。
