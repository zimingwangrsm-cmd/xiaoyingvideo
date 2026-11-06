# 统一契约 v1

任务书数据结构优先，JSON使用camelCase。Python兼容3.9/Pydantic v1。项目根路径由配置决定；服务端内部字段以`_`开头且不进入DTO。

## 时间与媒体模块契约
- `timeline.parse_srt(text: str, duration_ms: float) -> list[dict]`，每cue id=c001，startMs/endMs/text。
- `timeline.build_blocks(cues, total_frames: int) -> list[dict]`，id=s01起，clipStartFrame/clipEndFrame/order/cueIds/text/riskHints。句末或句组分块、合法帧间隙中点；无合法帧边界合并。全部块分割整个源。
- `timeline.build_spans(blocks, kept_ids) -> list[dict]`，sourceStartFrame/sourceEndFrame/outputStartFrame/blockIds。
- `timeline.map_cues(cues, spans, fps=30) -> list[dict]`；`write_srt(cues)->str`，`write_vtt(cues)->str`。
- `timeline.duration_ms(spans)->float`。异常采用ValueError带具体中文信息，根层转422。
- `media.probe_media(path)->dict`：durationMs/totalFrames/width/height/fps/hasAudio/audioStartMs/videoStartMs 等。
- `media.prepare_source(input_path, output_path)->dict`：验证<=180秒、音轨及支持偏移；生成规范H264/AAC 30fps/48kHz，<=720p档位，不放大。返回probe结果。
- `media.render_spans(source_path, spans, output_path, progress_callback=None, timeout=240)->dict`：一次filtergraph、临时文件校验后原子发布，callback(phase, progress可null)，返回实际probe；验时长误差<=100ms。
- `media.sha256_file(path)->str`。

## 项目DTO
遵循任务书Project，加`metrics:{plannedDurationMs,lockedDurationMs,targetStatus,keptCount,deletedCount}`、`source.videoUrl`、`source.subtitleUrl`、`sampleInfo:{origin,label,transcriptVerified}`、`suggestionMode`。时间和状态由后端计算。

## API
- GET /api/health => {status,mediaAvailable,mode,allowUploads,suggestionMode}
- GET /api/samples => {samples:[{id,title,description,origin,label,durationMs,transcriptVerified,recommendedLockedIds}]}
- POST /api/projects/from-sample {sampleId} => Project (201，样例可快速就绪)
- POST /api/projects/import multipart(video, subtitles) => Project (202,state=preparing)
- GET /api/projects/{id} => Project
- POST /api/projects/{id}/actions {expectedRevision,action} => Project
  action为set_target{targetMs} / lock,unlock,delete,restore{blockIds} / restore_all / undo / apply_proposal{proposalId}
- POST /api/projects/{id}/proposals {expectedRevision,mode?:rules|auto} => Proposal（同步；不自动应用）
- POST /api/projects/{id}/renders {expectedRevision,allowOverTarget:false} => RenderJob（202，可复用）
- GET /api/jobs/{id} => RenderJob，含isCurrent、artifact:{id,videoUrl,downloadUrl,srtUrl,vttUrl,recordUrl}或null。
- GET /api/projects/{id}/source/video，/source/subtitles?format=vtt
- GET /api/artifacts/{id}/video?download=1、/subtitles?format=srt|vtt、/record
- 错误HTTP 4xx/5xx => {error:{code,message,details?}}；409 revision冲突；404会话不拥有资源；422输入/约束。
- Cookie匿名会话HttpOnly SameSite=Lax；前端fetch同源携带cookie。localStorage仅存projectId；刷新GET恢复。
- 前端开始编辑后若revision!=snapshotRevision，旧文件只能查看上一版，当前下载按钮禁用；后端download=1与字幕/record下载也拒绝过期结果。
- set_target/lock/unlock/delete/restore/restore_all若实际选择完全未变化，返回原revision，不增加撤销历史、不使成片过期。旧expectedRevision仍先返回409。
- 替换素材尚未ready时，原可编辑项目继续作为刷新恢复点，并提供“返回上一个项目”；新素材ready后才切换持久恢复点。无旧项目时直接恢复新建项目。
- 同一DATA_DIR只允许一个服务进程持有文件锁；第二实例在恢复未完成任务之前拒绝启动，退出或崩溃后由操作系统释放锁。
- 模拟失败只在明确开发模式可用：请求头`X-Demo-Fail: render`或`proposal`，且服务器DEMO_TEST_FAILURES=true；默认不显示入口。

## 分工与文件边界
- 根代理：后端API、持久化、建议、启动、集成及交付。
- 媒体代理：timeline.py/media.py、相应测试、6秒工程样例脚本。
- 样例代理：原创脚本、TTS/卡片素材、prepare_sample.py、manifest；不编辑媒体模块。
- 前端代理：frontend/全部；在M1确认后开始搭界面，当前可检查依赖并设计契约接入。

## V2：精修、自动字幕与本机模型任务
- 导入 `subtitles` 可省略，新增 multipart `separateVoice`；缺SRT时本机ASR生成字幕及词时间轴。准备过程中Project.processPhase为preparing/separating/transcribing，失败保留原项目恢复入口；POST `/api/projects/{id}/retry-import` 可重试。
- Project schemaVersion=2 增加words（id/blockId/text/startMs/endMs/clipStartFrame/clipEndFrame/confidence）；edit增加order、deletedWordIds、captionEdits、wordEdits、notes、recordings、pendingRewrites。原源时间轴不变，order定义输出顺序。
- 首次V2编辑保留v1-before-upgrade.json；旧项目和旧成片仍可读。所有媒体修改沿用expectedRevision、撤销和过期下载保护。
- actions新增correct_caption{blockId,text}、correct_word{wordId,text}、annotate{blockId,text}、delete_words/restore_words{wordIds}、move_block{blockId,direction:-1|1}、set_rewrite{blockId,text}、restore_audio{blockId}。空text撤销对应校对/备注/改写。整段校对绑定完整时间，需清除后才能剪词；逐词校对保持原实测时间。
- POST `/api/projects/{id}/processing/{kind}` {expectedRevision,separateVoice?} => 202 ProcessingJob；kind为transcribe/separate/suggestions。GET `/api/processing-jobs/{id}`含status/phase/elapsedSeconds/result/error/isCurrent；与渲染Job分开。
- 转写结果只形成候选。POST `/api/projects/{id}/transcript/confirm` {expectedRevision,jobId}确认后建立新时间轴、清除旧编辑约束，并保存完整旧快照。并发编辑使候选过期。
- 本地模型建议包含strategy及items；item含id/blockId/type/before/after/reason/status/action/requiresRecording。POST `/api/projects/{id}/proposal-decisions` {expectedRevision,proposalId,itemIds,decision:accept|reject} => {project,proposal}；逐项接受更新剩余建议基准版本，人工另行编辑后剩余建议失效。
- POST `/api/projects/{id}/recordings` multipart(audio,expectedRevision,blockId,keepBackground=false) => 202 ProcessingJob。支持WAV/MP3/M4A≤30MB；不得长于原段，短音频补尾部静音。结果包含可试听audioUrl。POST `/recordings/confirm` {expectedRevision,jobId}才真正应用。
- 有pendingRewrites的保留片段不能渲染；补录应用或撤回改写后解除。补录不做声音克隆或口型同步。补录保留背景音要求先完成人声分离。
- GET `/api/projects/{id}/audio/vocals|background`、`/recordings/{recordingId}/audio`均校验项目会话。
- GET `/api/artifacts/{id}/bundle`下载MP4/SRT/VTT/JSON交接ZIP，同样拒绝过期产物；公开样例附署名与许可。JSON不是第三方编辑器原生工程格式。
- 本机模型URL只允许回环主机；处理任务真实失败可重试，LLM失败明确标记规则回退。VAD无可用语音时不生成假字幕。

## 2026-11-06 独立审阅优化补充

- `media.prepare_source(input_path, output_path, max_seconds=180)`：实际执行配置的 `MAX_SOURCE_SECONDS`，不得超过180秒。
- 编辑动作 `set_brief{text}` 保存用户的剪辑主线。非空时，本地模型逐段评估相关性和前后依赖，程序按实测帧预算选择候选；目标为上限，不保证填满。候选中的 `delete_block` 可有 `blockIds` 依赖组，整组作为一项原子确认，不能包含必留或未知ID。
- `POST /api/projects/{pid}/transcript/restore {expectedRevision,snapshotId}`：恢复所选识别快照及其编辑状态；新revision递增，当前状态先备份。Project增加 `transcriptRestorePoints` 元数据列表；恢复不直接恢复旧成片下载资格。
- 补录 POST 在任何落盘前检查 `allowUploads`；public返回403。仅相同项目、revision、片段、文件名、文件内容SHA256、keepBackground的活动任务可复用；其余返回409 `processing_busy`，不创建孤立录音目录。失败任务清理新建录音目录。
- 补录任务 DTO 的 `intent` 包含 blockId、blockText、fileName、keepBackground、原时长；确认结果标明补录时长。前端检查发起片段与返回片段一致。
- 草稿是浏览器页内的 projectId/blockId/field 状态，切项目保留且隔离；仅对应成功且未被后续输入改变的字段清草稿。刷新/关闭由离开提示保护，未承诺磁盘草稿持久化。
- local模式开放 `GET /delivery`、`GET /api/deliverables`、`GET /api/deliverables/{key}`；固定白名单，含文件大小与SHA256，MP4支持Range。public模式返回404。交付包不含private data目录或Cookie。
