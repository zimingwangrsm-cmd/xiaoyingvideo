# 口播精简｜小影产品概念 Demo

## V2更新

GitHub版本包含源码、报告正文和公开截图。完整PDF/HTML、视频和交付包保存在本地`deliverables/v2/`。

已新增本机自动字幕、字幕/词语校对、口误备注、真实剪词、整句重排、人工补录、人声分离和本地模型逐项建议。使用与安装见[README_V2.md](README_V2.md)，[新版验收步骤](deliverables/v2/ACCEPTANCE_GUIDE.md)，[完整图文报告](deliverables/v2/PRODUCT_REPORT.md)。下面保留V1基础运行说明；V2的字幕文件为可选。

独立本地网页，使用原始中文单人口播与SRT，以完整句组删减/恢复并导出真实MP4、SRT和修改记录。不是小影官方上线产品。

## 明天验收

服务端本机入口为 `http://127.0.0.1:8767`。详见 [五分钟验收步骤](deliverables/DEMO_ACCEPTANCE.md) 和 [实现审阅与修复](deliverables/IMPLEMENTATION_REVIEW.md)。同一数据目录只允许一个服务实例；启动脚本每次重建前端。

## 启动

Linux服务端（Windows可用WSL），Python 3.9以上、Node 20以上、FFmpeg/ffprobe。已验证的后端版本见requirements.txt。前端无外部依赖，不需要npm install。

```bash
cd /data1/wzm/wangyi/xiaoying_koubo
python -m pip install -r requirements.txt
cd frontend
npm run build
cd ..
bash scripts/run_demo.sh
```

默认地址 `http://127.0.0.1:8765`。默认端口被占用时自动尝试随后19个端口；也可设置 `PORT=8766`。不终止其他进程。
2026-11-06 已实际启动并通过 HTTP 与 Chrome 浏览器验收。本轮使用 `http://127.0.0.1:8767`；每次启动以终端打印地址为准。

远程Linux可从自己的电脑建立转发（替换占位符）：

```bash
ssh -L 8765:127.0.0.1:8765 <用户名>@<服务器地址>
```

然后在本机浏览器打开转发后的地址；转发端口需与实际服务端口一致。

## 素材与能力

- 首版输入：MP4≤100MB、≤180秒、含音轨；UTF-8/BOM SRT，完整句标点、无重叠越界。
- 输出：30fps、48kHz、H264/AAC、不超过720p档位，保持画幅；MP4字幕另附SRT，播放器使用同源VTT。
- 样例是原创脚本＋离线eSpeak NG普通中文合成旁白＋示例文字卡，136.567秒；不是用户真实经历或真人口播。
- `MODEL_MODE=rules`无需密钥。完整样例提供绑定视频/字幕哈希的重复提示；新输入采用保守规则。模型适配器尚无真实服务调用验证，私人上传默认不外发。
- `fixtures/README.md`记录素材来源和验证；没有人工逐字听审或真人切口验证。
- 首版使用原生ES modules代替React/Vite：离线缺少完整构建依赖，保留全部产品行为，Node只做静态构建与检查。

## 复现验证

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
cd frontend && npm run check
```

在工程根运行 `python scripts/export_examples.py`，可通过同一后端服务层生成90秒、60秒目标和全部恢复三个真实产物，无须HTTP。它证明媒体和状态链路，不替代浏览器验收。

生成样例需要Pillow和系统libespeak-ng；已附生成好的公开样例。重新生成：`python scripts/prepare_sample.py`。正常使用成品无需TTS依赖。

## 数据与部署

项目状态和上传在data中，以匿名会话隔离；不公开静态托管data。前端dist与API由同一进程提供。APP_MODE=public时只开放样例、关闭上传。无公开部署或收费服务开通。
用户指定同步仓库：https://github.com/zimingwangrsm-cmd/xiaoyingvideo 。源码包排除data、密钥、缓存与临时TTS产物。录屏、截图、PDF与媒体文件保留在本地交付目录，不提交大文件。

## 当前交付状态

43项后端/媒体/服务层测试和9项前端状态/模板测试已通过。最新真实 HTTP、21组 Chrome 浏览器检查、实际服务重启验收，详见 `deliverables/VALIDATION.md`。171.44秒带播放声音的真实录屏和截图位于本地 `deliverables/`。个人经历一题仍等待用户真实输入。

## HTTP、浏览器与录屏复现

也可在允许socket的普通终端运行一条命令，自动构建、启动、HTTP检查并保留服务供浏览器操作：

```bash
cd /data1/wzm/wangyi/xiaoying_koubo
python scripts/local_acceptance.py
```

只检查后退出：追加`--check-only`。只停止本脚本创建的进程，不会结束未知服务。详细结果写入deliverables/local_run_receipt.json与http_check_console.log。已实际通过；回环检查显式禁用环境 HTTP 代理，避免本地请求被错误转发。

启动后以终端打印地址为准，执行 `python scripts/check_http.py --url http://127.0.0.1:8765`。只有所有检查成功才生成 `deliverables/http_validation.json`。本轮成功证据见该文件；浏览器验收单独记在 `browser_validation.json`。


浏览器脚本需要 Playwright 1.55.0（或兼容版本）和支持 H.264/AAC 的 Chrome。本机缓存的 Chromium 缺少这两种解码器，已使用临时目录中的 Chrome 157.0.8103.38 实测。设置 `PLAYWRIGHT_MODULE` 为可用模块路径，`CHROME_EXECUTABLE` 为浏览器路径，`APP_URL` 为实际回环地址。配置目录不可写时，可将 `XDG_CONFIG_HOME`、`XDG_CACHE_HOME` 指向临时目录。

```bash
# 独立验收数据；只在此验收服务中开启明确的故障注入。
DATA_DIR=data/acceptance_20261106 DEMO_TEST_FAILURES=true python scripts/local_acceptance.py --port 8767
# 另一个终端，先设置上文浏览器环境变量：
node scripts/check_browser.cjs
# 停止上述服务，再以同一 DATA_DIR 和同一端口启动（不再启用故障注入）：
DATA_DIR=data/acceptance_20261106 python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8767 --workers 1
node scripts/check_restart.cjs
```

`check_browser.cjs` 真正点击界面、上传文件、播放媒体并下载；失败用例仅通过既有开发测试请求头触发，未伪造 HTTP 返回。Cookie 和重启恢复状态仅写入被忽略的 `data/browser_acceptance/`。

录屏使用独立 Xvfb（1440×1000）、PulseAudio 与 FFmpeg。设置 `XVFB_EXECUTABLE` 为可用 Xvfb 路径，运行 `node scripts/record_walkthrough.cjs`；脚本在同一进程环境启动虚拟桌面和采集器，避免跨 IPC 命名空间的共享内存问题。脚本采集真实桌面和隔离的浏览器播放声音，包含实际渲染等待，无剪接、倍速或替换配音；每次会覆盖 `deliverables/walkthrough.mp4`。本地样例已经准备好，不要重生成现有样例。

五页草稿由 `scripts/build_brief.py` 生成，需要ReportLab及脚本所用中文字体；本机可用 `/usr/bin/python3 scripts/build_brief.py`。截图、录屏、PDF、原MP4与本地source.zip不随Git同步，交付时使用本地文件。
