# 口播精简实施进度

## 当前：公网完整Demo部署（2026-11-07）
- 公网入口：https://con-chip-variable-sleeping.trycloudflare.com，完整上传、识别、建议、录音、分离、导出已通过外网浏览器实际验收。
- 独立快照与公网数据目录，模型8783/web8768/HTTPS隧道由systemd用户服务管理，开机启用，原8767保留。
- 72项后端、16项前端检查通过；web被终止后6.24秒自动恢复，项目与下载保留、公网地址不变。
- 部署包留在data/deploy/koubo-web-runtime.tar.gz，不设公开源码包下载入口；临时域名在隧道重建后可能变化。
- 详情见deliverables/deployment/README.md、deploy/README.md。

## 最终交付（2026-11-07）
- 应用核心fce60bf整合538fa8e兼容性修复并适配交付机FFmpeg4.2；干净依赖环境67项后端、16项前端、构建与compileall通过。
- 同版本真实Qwen148.2秒/32项候选；连续录屏171.56秒/4289帧/实际声音；本轮导出27.588秒/827帧/6段，区别于历史AI全接受25.188秒。
- 五页产品说明和两页AI记录已从用户审阅稿更新、渲染；个人核心表述保留。八图流程、离线HTML、许可和哈希清单组成最终包。
- 领取入口：deliverables/final_submission/README.md；8767/delivery亦提供附件。本机网页不冒充评审公网入口，平台提交由本人执行。
- 以下为历史功能实施记录，不与最终环境测试口径混算。

## 当前：句子录音与双栏建议（2026-11-07）
- 补录上限已放宽到60秒：直接录音自动停止，上传后端校验；长于原句延长末帧、保留完整音频，预计时长和字幕随之更新。验证见deliverables/minute_recording。
- 每句直接录音/上传、试听与确认；麦克风取消/结束释放、时长封顶、草稿按项目和句子隔离。
- 右侧文稿/建议切换、建议内部滚动及状态筛选，左侧预览。
- 入口仍为8767、data/acceptance_20261106；详细验证见deliverables/recording_layout/RELEASE.md。
- 下方2026-11-06内容为上一轮基线。

## 当前：独立审阅优化版（2026-11-06）
- 本轮从70e3b6e增量实施0166eb6独立审阅意见；详细见deliverables/optimization/REVIEW_RESPONSE.md。
- 修复草稿丢失/串项目、补录请求串任务、public上传绕过、配置时长上限；加入识别版本恢复和固定模型下载。
- 精修三组、播放/滚动/焦点保持、切口循环试听、预检、页内草稿与最近项目返回。
- 63项后端、14项前端、桌面与手机尺寸完整浏览器任务通过；真实模型与确定性交互分开记录。
- 真实AI任务粗剪128.2→25.188秒（80.35%），5段主线；专名字幕未人工校对、未宣称作者听审通过。
- 当前使用data/acceptance_20261106、Web8767、模型8781；交付中心/delivery提供报告、前后视频和交付包，仅回环/SSH，不是公网部署。
- 下面V1/V2数量与录屏为历史基线。原始需求范围以REQUIREMENTS_TRACE.md为准；真人新录音、质量真值和用户研究仍待人工完成。

## V2已完成（2026-11-06）
- 按advice.md和已确认范围实现：CPU本机自动字幕、精修/备注、实测词剪辑、整句重排、人工补录保持画面时长、人声分离、本地Qwen策略与逐项接受/拒绝/全部接受。
- 实际入口仍为http://127.0.0.1:8767；本地模型http://127.0.0.1:8781，故障注入关闭。启动见README_V2.md、scripts/run_v2.sh。
- 两条公开授权真人素材为Wikitongues Tao/Ying，CC BY-SA 4.0；原合成样例与哈希未改。真人字幕实际由medium CPU识别，存在口音和专名错误，保留待校对标识。
- 57项后端、9项前端、21组原流程及12组V2浏览器检查通过；HTTP、V2真实重启和V1读取兼容通过。详见deliverables/v2/FINAL_VALIDATION.md。
- 本地模型用JSON Schema限制操作类型与片段ID，程序计算每项和整体预计时长；失败明确回退规则，不把无效模型输出直接应用。
- 新版连续真实录屏171.04秒，含实际浏览器声音、转写、模型建议、确认、渲染和下载，位于deliverables/v2/walkthrough.mp4。
- 完整报告Markdown/PDF/离线HTML及五页摘要在deliverables/v2；含旧版基线、四个竞品的公开官方资料和新版实际截图。竞品未冒充登录账号实测。
- 发布完成条件：用户已在自动审批拒绝后明确允许公开上传报告截图；本次发布包含源码、报告正文和25张已检查的公开截图，模型与大媒体继续保留本地。
- 模型权重、venv与私人状态在Git忽略目录；原V1 JSON状态备份在data/v1_state_before_v2，cookie不进入交付。
- 需保留的边界：不做同声线合成或口型同步；补录测试用授权原片片段；没有人工真值的准确率/自然度指标。分离后识别可能更差，报告已给出真实错例。

## V1已完成状态（2026-11-06）
- 最新复审：修复重复启动干扰任务、无变化操作使成片过期、失败导入丢失原项目入口；启动时重建前端。详见`deliverables/IMPLEMENTATION_REVIEW.md`。
- 明天验收入口与五分钟操作步骤：`deliverables/DEMO_ACCEPTANCE.md`。正常服务已更新到本轮代码，关闭故障注入。
- 最新验证：43项Python测试（23.43秒）、9项前端测试、21组真实Chrome检查、HTTP及实际服务重启通过。新增报告位于`deliverables/review/browser_validation.json`。
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
