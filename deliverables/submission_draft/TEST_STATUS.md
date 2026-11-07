# 版本与隔离复验状态

以下保留原版失败证据，不是最新修复后的最终验收报告。原复验基线：`b83784d7371a9fcd8da7a2be131a66c0e7748099`。

## 版本范围

- 原隔离复验：b83784d，以下失败与诊断结果仅对应此版本。
- 后续 main：1c2ed70，新增每句 60 秒补录、末帧延长和字幕顺延；发布记录声明 65 项后端与 16 项前端检查，属其原环境结果。
- 本轮兼容性修复：基于 1c2ed70，独立分支 fix/runtime-compat-20261107 的 538fa8e 已完成下述隔离复验。没有把旧版失败直接推断为新版所有环境失败。

## 本轮兼容性修复复验

修复基于 main `1c2ed70a949db7de3c1b156539810bcc1fd4e067`，修复提交：[538fa8e9da2dcaaec3b25520dc7360bbde036eb9](https://github.com/zimingwangrsm-cmd/xiaoyingvideo/commit/538fa8e9da2dcaaec3b25520dc7360bbde036eb9)。

- Python 3.12.14、FFmpeg 7.1.5、FastAPI 0.100.0、Pydantic 1.10.26。
- 后端 67 项通过，43.80 秒；一个非失败的 AnyIO 弃用警告。
- 前端 16 项检查、静态构建与 compileall 通过。
- FastAPI TestClient 真实导入 → 删除中间句 → FFmpeg 导出 120 帧、30fps → 下载字节比对通过。
- 含 60 秒补录回归；语音推理使用测试替身，未把确定性测试写成真实 ASR/LLM 验收。

这是修复分支的隔离复验结果，不是 main 已合并、目标机器已部署、真实浏览器已完成全链路或真人听审通过。最终 Demo 仍需按 REVIEW_AND_HANDOFF.md 在交付环境检查。

## 原样测试

- 环境：Python 3.12、FFmpeg 7.1.5；测试使用临时依赖目录，pytest 8.3.5。
- 执行原样后端测试：`PYTHONPATH=<临时依赖目录> python -m pytest tests -q`。
- 结果：17 passed、46 errors。46 个错误来自同一工程视频 fixture 的输出校验失败，不是 46 个独立产品缺陷。

## 真实服务复现

由于锁定的 Pydantic 1.10.12 在此 Python 3.12 环境无法启动，HTTP 复现使用环境中的 FastAPI 0.141.1 / Pydantic 2.13.4。此依赖差异必须保留，不等同按原锁定环境验收。

FastAPI TestClient 调用真实服务和 FFmpeg，没有模型推理，仅用规则模式：

1. 导入 6 秒 H.264/AAC 工程视频及 SRT，返回 202，最终状态 ready。
2. 删除中间句 s02，返回 200。
3. 发起保留 s01 与 s03 的 4 秒渲染，返回 202；最终任务 failed、errorCode 为 `render_failed`。
4. 错误信息：“规范视频需要 30 fps 和 48 kHz 音轨。”

原始 concat 输出 120 帧，r_frame_rate 为 30/1，但 avg_frame_rate 为 120000000/3966667，约 30.2521。当前媒体校验使用平均帧率严格判断，因此拒绝该结果。

## 诊断实验不是修复验收

只在临时进程内给编码参数注入 `-r 30 -fps_mode cfr` 后，同例变成 120 帧、4 秒、30 fps，导出成功；未改仓库源码。这支持编码输出时序与校验冲突的定位，但不能写为正式修复完成。

诊断注入后测试为 61 passed、2 failed。剩余两项涉及新版 FFmpeg 下测试 fixture 旋转元数据未写入，以及 AAC 时长恰好 4000ms 与测试硬断言大于 4000ms 不一致。此结果不能替代原实现的 17 passed / 46 errors，也不是全部通过。

## 结论限制

- 原基线隔离环境真实导出失败，不能拿该次结果宣称完整任务验收通过。
- 此问题在旧实现中已有，不能称为句子录音或新版布局引入的回归。
- 未证明所有 FFmpeg 版本或既有部署环境都失败。
- 修复复验需独立列明版本与结果，最终 Demo 还需在实际交付环境检查浏览器播放、补录和下载。

## 修复原始报告

- [兼容性修复说明](https://github.com/zimingwangrsm-cmd/xiaoyingvideo/blob/538fa8e9da2dcaaec3b25520dc7360bbde036eb9/deliverables/compatibility/README.md)
- [机器可读验证记录](https://github.com/zimingwangrsm-cmd/xiaoyingvideo/blob/538fa8e9da2dcaaec3b25520dc7360bbde036eb9/deliverables/compatibility/validation.json)

此提交没有 GitHub Actions 运行，不宣称远端 CI 通过。
