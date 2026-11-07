# 最终交付验证（2026-11-07）

应用核心固定提交：`fce60bfcbaf96a4b2574bc6b582753d0561f4424`。基于main 1c2ed70整合修复538fa8e；文档只取cd063651中的submission_draft目录，未使用文档分支的旧应用。最终交付提交另增加附件、复现脚本和交付中心白名单，不改变录屏中的编辑/渲染核心。

## 当前环境复验

| 层级 | 当前结果 | 证据与边界 |
|---|---|---|
| 干净Web依赖环境 | Python3.9.13，FastAPI0.100.0，Pydantic1.10.26，pytest8.3.5 | environment.json、runtime_packages.txt；data/final_runtime未继承site-packages |
| 媒体与后端 | 67项通过，57.02秒；compileall通过 | 真实FFmpeg4.2.7；ASR/LLM在单元测试中为显式测试替身 |
| 编码兼容 | 显式30fps CFR；旧版使用vsync，新版使用fps_mode | 保留精确帧数/FPS检查，未放宽验证；FFmpeg7.1.5的原修复报告单独保留 |
| 前端 | 16项检查和构建通过 | 含录音WAV边界、取消后迟到流释放、草稿隔离、版本下载保护 |
| HTTP | TestClient实际导入→删句→120帧30fps渲染→下载字节匹配 | test_http_compat.py；不是浏览器或真人听审 |
| 浏览器新流程 | 草稿、网络失败、迟到保存、跨项目、多项接受/拒绝、手机补录/导出通过 | browser_regression.json；确定性候选用于交互，真实ASR/渲染；手机为模拟尺寸 |
| 旧流程浏览器 | 21组通过：导入、保护、撤销、失败重试、迟到/旧成片与下载 | legacy_browser_validation.json；独立规则服务启用明确测试故障头，录制服务关闭 |
| 实际分钟录音 | 连续录制约60秒自动停止，2.6秒原句被60秒录音替换，末帧延长并实际下载 | minute_check/browser_validation.json；浏览器测试麦克风，不是物理麦克风测评 |
| 媒体边界回归 | 短补录、3秒替换2秒、60秒、60.1秒拒绝、尾音、逐帧末帧延长、字幕顺延、剪词、恢复、必留/撤销/版本 | 当前67项后端与浏览器记录分别覆盖；未把模拟推理算成真实模型 |
| 实际Qwen | 148.2秒、32项候选 | real_inference.json；准备阶段通过真实界面发起，未以fixture代替 |
| 最终实际成片 | 27.588秒、827帧、30fps，6段；MP4/SRT哈希与记录一致 | media_validation.json、demo_edit_record.json；接受/拒绝及手动恢复后的结果，区别于历史25.188秒 |
| 连续录屏 | 171.56秒、4289帧，H.264/AAC，实际浏览器声音均值-30.4dB | recording_validation.json；无拼接/倍速，模型等待在录屏前并明示 |
| 完整播放 | Chrome经真实HTTP播放至ended，4289帧，无媒体错误；FFmpeg完整解码无错误 | full_playback_validation.json；自动播放不等于人工听审 |
| 文档 | 产品说明PDF5页、AI记录PDF2页、截图流程PDF8页 | DOCX模板原文个人段落逐段保留；五页已逐页渲染检查 |

模型沿用runtime_manifest固定revision/SHA：本轮再次验证全部6个Whisper/Qwen清单文件。Demucs为既有锁定组件，本轮不重复声明分离质量评估。详细模型来源见model_manifest.json。

## 录屏和截图真实性

录屏由Xvfb与FFmpeg连续采集，浏览器真实操作。固定顶部横条是明确的录屏说明，不是伪造系统反馈。补录是授权样例输入的测试设备；最后恢复原声，避免把测试音频当最终作者表达。失败恢复由浏览器仅中断一次请求触发，录制服务DEMO_TEST_FAILURES=false。

第2、6、8张截图在同一版本下重新复现，便于看清错误反馈和已解码的预览；不是声称八张图均取自录屏帧。首轮旧浏览器脚本曾因新增文稿标签隐藏控件而停止，已加入真实切换标签动作后复验，未改产品状态或伪造响应。

## 可访问性和发布

交付形式为可下载附件、离线HTML和公开GitHub文件，不承诺公共Web应用。ZIP不含data目录、Cookie、密钥、模型权重或私人录音。MANIFEST逐文件给出大小和SHA256；PUBLIC_ACCESS.json在上传后记录匿名下载结果，并与ZIP分开提供，避免循环哈希。

本地领取入口仍是8767的/delivery。最终上传招聘平台由本人执行；个人观点保留提交前本人核对提示。专名字幕、语义保真及音质仍需作者人工检查，不从通过数量推导质量或商业价值。

GitHub连接器的整包上传返回HTTP500，公开ZIP改由专用交付分支的GitHub归档提供。归档只含最终附件；本地submission_package.zip与归档的各文件由同一MANIFEST核对，不要求ZIP容器字节相同。
