# V2最终验收

- 后端57项测试、前端9项测试通过。
- 原流程21组、新V2流程12组真实Chrome检查通过；ASR、Demucs与Qwen均为实际本机调用。
- HTTP 200/206/416、HEAD/后缀Range、会话隔离、同源下载哈希通过；V2实际重启后编辑与成片保留。
- 升级后原V1项目revision/编辑不变，旧产物可读取。原状态已在私有data目录备份。
- 连续录屏171.04秒、4276帧、实际浏览器播放声音；视频码流保持，音频按采集时间戳归整。
- 正常入口8767，模型只监听本机8781，故障注入关闭。

真实限制：方言与专名误识别仍需校对；分离可产生新错误。当前没有人工真值的整体准确率或真人自然度结论。补录接口测试使用公开授权原片片段，未冒充新录音。

证据：acceptance/browser_validation.json、legacy_checks/browser_validation.json、http_validation.json、speech_validation.json、bgm_validation.json、restart_validation.json、migration_validation.json、recording_validation.json。模型结构约束的最终复核与逐项接受也包含在连续录屏中。
