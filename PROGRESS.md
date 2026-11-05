# 口播精简实施进度

## 当前状态（2026-11-06）
- 本轮按要求复用已有工程，没有重开发产品功能。
- HTTP、真实 Chrome 浏览器、服务停止再启动验收已通过；真实录屏171.44秒、4286帧，带浏览器播放声音，完整性及同步抽查通过，见 `deliverables/recording_validation.json`。
- 本轮实际服务：`http://127.0.0.1:8767`，数据目录 `data/acceptance_20261106`；默认启动仍用 `scripts/run_demo.sh` 自动选择空闲端口。
- 既有原创样例136.567秒，原MP4/SRT哈希未改变。没有真人素材、模型密钥或用户真实产品经历，继续明确使用合成旁白与规则建议。

## 本轮完成与证据
- `deliverables/http_validation.json`：真实200/206/416、后缀Range、HEAD、双Cookie隔离、MP4/SRT哈希、过期下载拒绝且预览可用。
- `deliverables/browser_validation.json`：19组真实Chrome检查；样例、锁定冲突、建议确认、恢复撤销、源/成片H.264/AAC和VTT、下载、失败重试、布局、合法/无效上传等通过。
- `deliverables/restart_validation.json`：实际停止并重启服务后，原Cookie、revision、edit和已完成成片仍可用，浏览器恢复与播放通过。
- `deliverables/browser_*.png`：实际页面截图，包含开始、工作台、冲突、建议、失败、结果、旧结果、手机布局和上传错误。
- `deliverables/browser_download.mp4`及同名前缀SRT/记录：浏览器实际下载，视频77.988秒，SHA256匹配记录。
- `scripts/record_walkthrough.cjs`：真实Xvfb桌面和隔离PulseAudio声音采集；同一进程环境启动，校验120–180秒、帧数与实际音量后才写成功记录。
- `deliverables/product_brief.pdf`：五页草稿，补入真实结果页截图；真实个人经历仍待本人提供。
- 本轮复核：41项Python测试（22.58秒）、9项前端测试、静态构建通过；新增验收/录屏脚本语法通过。

## 环境问题及处理
- 历史socket EPERM本轮已解除，不再是阻塞。
- 环境HTTP代理导致第一次健康检查误判；仅在两个本地验收脚本用ProxyHandler({})强制回环直连。
- 缓存Chromium缺少H.264/AAC解码器。使用 `/tmp/koubo-browser/opt/google/chrome/chrome`（157.0.8103.38）和已缓存Playwright 1.55.0实测，没有更改产品编码。
- Xvfb与FFmpeg跨工具进程的IPC命名空间造成首次录屏只剩3帧；这份失败文件不作为成果。改为同一脚本启动虚拟桌面和采集器，并加入实际文件检查。
- Git远程已由用户指定为 `https://github.com/zimingwangrsm-cmd/xiaoyingvideo`，main原仅有初始README。保留远程初始提交，追加现有工程与验收证据；作者沿用远程已有的cangsheng。录屏、照片、缓存、Cookie、数据和大媒体文件不入Git。

## 恢复方式
1. 先读本文件与API_CONTRACT.md，不重选型或重生成现有样例。
2. 默认使用：`bash scripts/run_demo.sh`。恢复本轮验收数据：`DATA_DIR=data/acceptance_20261106 PORT=8767 bash scripts/run_demo.sh`；以实际输出端口为准。
3. HTTP复验：`python scripts/check_http.py --url http://127.0.0.1:<实际端口>`。
4. 浏览器脚本需要设置 `APP_URL`、`PLAYWRIGHT_MODULE`、`CHROME_EXECUTABLE`；完整步骤见README。失败恢复验收需要独立服务显式设置 `DEMO_TEST_FAILURES=true`，正常运行关闭。
5. 重启验收Cookie仅保存在被忽略的 `data/browser_acceptance/storage.json`，不能加入源码包或Git。
6. 录屏脚本需要Xvfb、PulseAudio与FFmpeg，`XVFB_EXECUTABLE`可指定临时Xvfb路径；不要将脚本运行结束等同录屏成功，以生成文件的校验记录为准。

## 尚需用户补充
- 最喜欢的产品/功能及近期真实使用经历，用于五页材料定稿；不影响已完成的技术验收。
- 人工逐字听审与真人口播切口自然度未验证；transcriptVerified=false保持不变。
- 未公开部署、开通付费服务或最终交卷。
