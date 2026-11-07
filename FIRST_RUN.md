# 首次运行编辑器

只查看最终演示、报告和截图：下载[提交附件包](https://codeload.github.com/zimingwangrsm-cmd/xiaoyingvideo/zip/refs/heads/delivery-reviewed-20261107)，解压后打开 START_HERE.html。附件包是离线展示材料，不包含编辑器源码或模型。

## 不下载模型，先完成一次真实剪辑

需要 Linux / WSL、Python 3.12、Node 20+、FFmpeg 5.1+ 和 ffprobe。下面的步骤在 Python 3.12、Node 24、FFmpeg 7.1.5 环境复验；FFmpeg需包含 libx264/AAC。

先下载本仓库**源码**并解压，在根目录运行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PORT=8767 MODEL_MODE=rules bash scripts/run_demo.sh
```

打开终端打印的本机地址。默认只监听127.0.0.1；端口被占用时会选择其他端口，以实际输出为准。停止服务用 Ctrl+C。

1. 导入源码中 `deliverables/final_submission/demo_result.mp4` 和 `demo_result.srt`。这是已公开的27.588秒剪辑结果，用于立即试用，不是128.2秒原始真人素材。
2. 在工作台设定必留内容，删除一句，再撤销或恢复。
3. 生成短片，播放结果，下载MP4和SRT。可继续编辑并重新生成。

这条路径不需要ASR、LLM、eSpeak或Pillow。自带字幕可直接使用；规则建议与手工剪辑可运行。无SRT自动识别、直接录音后的识别、分离及本地模型建议需要下方的完整环境。

## 更多样例与完整AI能力

- 源码不包含原始真人视频或模型权重。已有样例媒体不会被启动脚本覆盖。
- 生成原创合成样例：按[素材说明](fixtures/README.md)安装 Pillow、eSpeak NG普通话数据与中文字体，再运行 `PREPARE_SAMPLE=1 PORT=8767 bash scripts/run_demo.sh`。显式请求生成失败时会停止，不会伪装成成功。
- 本地ASR、分离、Qwen模型及真人原始素材的准备步骤见 [README_V2.md](README_V2.md) 和 [fixtures/README.md](fixtures/README.md)。下载与首次推理需要额外时间和磁盘；不在普通启动时自动下载。
- 在自己的素材上操作前，确认拥有使用权限；数据保存在本机 `data/` 或 `DATA_DIR` 指定目录。同一个数据目录仅运行一个实例。
