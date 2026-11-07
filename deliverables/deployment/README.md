# 可直接使用的公网网页版

**入口：[https://con-chip-variable-sleeping.trycloudflare.com](https://con-chip-variable-sleeping.trycloudflare.com)**

不用SSH转发；可以直接上传MP4，自动识别字幕，按词/按句精剪，使用真实本地模型建议，直接录音或上传补录，人声分离，播放并下载实际MP4/SRT。首次录音请允许浏览器麦克风权限。

## 已部署与验证

- 模型、完整后端和HTTPS入口由三个用户级systemd服务常驻，均已启用开机启动；用户linger已开启。
- 72项后端、16项前端检查通过。公网浏览器实际完成无SRT上传/ASR、剪词、麦克风WAV提交/识别/确认、Demucs分离、渲染下载、Qwen建议、Range播放及会话隔离。
- Qwen本轮实际耗时187.5秒。浏览器录音使用授权测试音频设备，未冒充物理麦克风或人工音质评测。
- 主动终止空闲web进程后，systemd在6.24秒内恢复ready；公网URL未变，浏览器项目、revision和成片下载仍可用。
- 公网项目保存在独立的data/deploy/public-data；原来的8767工作台和数据继续保留。

## 使用与容量

视频≤90MB、≤180秒；每句补录≤60秒。每会话10项目、总计50项目、最多3个处理任务、10GB演示存储预算。超限时明确提示，已保存编辑仍保留。

这是[Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)临时域名，无生产可用性保证；隧道进程重建后域名会变化。当前地址由data/deploy/runtime/tunnel.json记录；需要固定域名时提供域名或命名隧道配置即可继续绑定。

## 部署包和维护

本地打包文件：`data/deploy/koubo-web-runtime.tar.gz`（约35MB）。包含可运行后端、构建后的网页、授权样例和安装/服务脚本，不含私人项目、Cookie、模型权重。模型依赖按固定清单准备。源码包不设公网下载入口，由维护者通过SSH/SFTP领取。

[部署与维护步骤](../../deploy/README.md) · [公网功能验收](public_validation.json) · [自动恢复验收](recovery_validation.json) · [部署版本与包哈希](DEPLOYMENT.json)
