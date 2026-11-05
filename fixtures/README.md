# 可复现的演示素材

`interview_intro_v1/` 是“面试项目介绍精简示例”。文字来自交接书第 5.2 章的 13 段原创脚本，保存在 `script.json`；其中的第一人称内容只是演示叙述。画面是代码排版的中文文字卡，声音是本机 eSpeak NG `cmn` 普通话合成旁白。没有使用真人录音、肖像、私人素材、声音克隆或在线 TTS。

随项目提供的版本为 **136.567 秒、4097 帧、约 2.9 MB**。实际必留 `s03/s04/s05` 共 **35.267 秒**；更换样例后必须重新计算。

- `canonical.mp4`：1280×720、30 fps、H.264、48 kHz AAC；每段显示编号，源视频时间与底部标记持续变化，可观察真实切片。
- `sample.srt`：13 条字幕，每条对应一个完整语义块。`s05` 的建议和适用范围在同一条字幕内。
- `manifest.json`：实际文件 SHA-256、实际帧数、逐段 WAV 采样数和时长、来源、校正状态、建议绑定哈希与建议必留项。
- `script.json`：原创文本和语义用途；可审阅和复现，不能把脚本中的演示经历当成用户经历。

## 离线生成

需要 Python 3.9+、Pillow、FFmpeg/ffprobe、Noto Sans CJK 字体，以及本地 eSpeak NG 库和普通话数据。Ubuntu 对应系统包为 `ffmpeg`、`fonts-noto-cjk`、`libespeak-ng1`、`espeak-ng-data`；不需要 `espeak-ng` 命令行程序。脚本通过 `ctypes` 调用本地共享库，不下载模型，不上传内容，不需要 API 密钥。

在项目根目录运行：

```bash
python scripts/prepare_sample.py
```

默认输出到 `fixtures/interview_intro_v1/`。可用 `--output /path/to/sample` 输出独立副本；`--keep-work` 保留每段原始与 48 kHz WAV、文字卡、完整 WAV 等中间文件到输出目录的 `_work/`（已忽略，不应提交）。`--rate` 默认为 180；它设置 TTS 合成语速，没有对录音做倍速处理。更换库版本、字体或编码器后，生成字节及哈希可能变化，须使用本次生成的 manifest。

脚本先分别合成每段 WAV，直接读取实际采样数，再重采样至 48 kHz。每段音频时长向上补齐为 30 fps 的整帧，前后各留 8 帧静音。字幕起止取自这些实测边界；SRT 的整数毫秒向内取整，避免切点偏一帧。段间静音中点恰好是分块边界。视频先独立编码，再与完整 WAV 封装，以保留最后一句的完整音轨。最终音视频完整解码一次，并验证帧数、采样率以及视频和音轨各自的时长。源视频内容上限为 180 秒。

## 校正与能力边界

`transcriptVerified` 保持 `false`。`ttsInputMatchesSrt=true` 仅表示合成请求与字幕使用了逐字相同的原文，不表示合成器正确读出了每一个字。时间码来自实际音频，尚未进行人工逐字听审；人工审校后才能改变该状态，若需改字幕应同时更新字幕哈希及建议绑定。

此样例具有真实中文语音和语义内容，可验证文字删减、必留约束、恢复、字幕映射与媒体导出。eSpeak 的音色较机械；真人口播的切口自然度需要另外使用已授权真人素材验证。

建议必留为 `s03`、`s04`、`s05`，它们的总时长应由当前实际视频分块计算。预设规则只适用于 manifest 中源视频和字幕哈希都匹配的这个样例。`preparedSuggestionSource=rules` 明确表示规则来源，没有声称运行过文本模型。

## 来源和许可记录

原创脚本用于本项目演示，文字卡由 `prepare_sample.py` 原创绘制。eSpeak NG 引擎和普通话数据来自本机系统包，当前版本记录在 manifest 中；引擎许可为 GPL-3.0-or-later，依据本机 `/usr/share/doc/libespeak-ng1/copyright`。上游为 [eSpeak NG](https://github.com/espeak-ng/espeak-ng)。脚本调用已安装库，仓库没有捆绑引擎或数据二进制；声音属于通用合成音色。

文字卡使用 Noto Sans CJK，字体许可为 SIL Open Font License 1.1，依据 `/usr/share/doc/fonts-noto-cjk/copyright`。仓库只包含渲染后的画面，没有捆绑字体文件。manifest 分别记录引擎、字体与原创内容来源，不把引擎许可写成真人录音授权。
