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
- 模拟失败只在明确开发模式可用：请求头`X-Demo-Fail: render`或`proposal`，且服务器DEMO_TEST_FAILURES=true；默认不显示入口。

## 分工与文件边界
- 根代理：后端API、持久化、建议、启动、集成及交付。
- 媒体代理：timeline.py/media.py、相应测试、6秒工程样例脚本。
- 样例代理：原创脚本、TTS/卡片素材、prepare_sample.py、manifest；不编辑媒体模块。
- 前端代理：frontend/全部；在M1确认后开始搭界面，当前可检查依赖并设计契约接入。
