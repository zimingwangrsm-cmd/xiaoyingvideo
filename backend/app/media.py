"""Bounded FFmpeg operations; no shell interpolation and no partial artifacts."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from fractions import Fraction

FPS = 30
SAMPLE_RATE = 48000
MAX_SECONDS = 180


def _run(arguments, timeout=60):
    try:
        result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        raise ValueError("媒体处理工具未安装，当前无法处理视频。")
    except subprocess.TimeoutExpired:
        raise ValueError("视频处理超时，请重试或使用更短的素材。")
    if result.returncode:
        # Decoder logs contain local paths; keep these out of user-facing errors.
        raise ValueError("媒体文件无法读取或处理，请确认 MP4 中的视频和声音可正常播放。")
    return result.stdout


def _float(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _known_time(value):
    return value is not None and math.isfinite(_float(value, float("nan")))


def probe_media(path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ValueError("找不到需要处理的视频文件。")
    payload = json.loads(_run(["ffprobe", "-v", "error", "-threads", "2", "-show_streams",
                              "-show_format", "-of", "json", str(path)], timeout=45))
    videos = [stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"
              and not stream.get("disposition", {}).get("attached_pic")]
    audios = [stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"]
    if not videos:
        raise ValueError("文件没有可用视频画面，请选择有效 MP4。")
    video, audio = videos[0], audios[0] if audios else None
    try:
        fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    if fps <= 0:
        raise ValueError("无法确定视频帧率，请重新导出 MP4。")
    fmt = payload.get("format", {})
    duration = _float(fmt.get("duration"), _float(video.get("duration")))
    if duration <= 0:
        raise ValueError("无法确定视频时长，请重新导出 MP4。")
    frames = int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else int(round(_float(video.get("duration"), duration) * fps))
    rotation = _float(video.get("tags", {}).get("rotate"))
    for item in video.get("side_data_list", []):
        if "rotation" in item:
            rotation = _float(item["rotation"])
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    if width < 2 or height < 2 or frames < 1:
        raise ValueError("视频尺寸或帧数无效。")
    try:
        sar = float(Fraction(video.get("sample_aspect_ratio", "1:1").replace(":", "/")))
    except (ValueError, ZeroDivisionError):
        sar = 1.0
    if sar <= 0:
        sar = 1.0
    display_width, display_height = max(2, round(width * sar)), height
    if abs(round(rotation)) % 180 == 90:
        display_width, display_height = display_height, display_width
    return {"durationMs": duration * 1000, "totalFrames": frames, "width": width, "height": height,
            "displayWidth": display_width, "displayHeight": display_height, "fps": fps,
            "hasAudio": bool(audio), "audioStartMs": _float(audio.get("start_time")) * 1000 if audio else None,
            "videoStartMs": _float(video.get("start_time")) * 1000,
            "formatStartMs": _float(fmt.get("start_time")) * 1000,
            "audioSampleRate": int(audio.get("sample_rate", 0)) if audio else None,
            "videoStartKnown": _known_time(video.get("start_time")),
            "audioStartKnown": _known_time(audio.get("start_time")) if audio else False,
            "formatStartKnown": _known_time(fmt.get("start_time")),
            "videoCodec": video.get("codec_name"), "audioCodec": audio.get("codec_name") if audio else None,
            "pixelFormat": video.get("pix_fmt"), "rotation": rotation,
            "videoStreamIndex": video["index"], "audioStreamIndex": audio["index"] if audio else None,
            "formatName": fmt.get("format_name", ""),
            "videoDurationMs": _float(video.get("duration"), duration) * 1000,
            "audioDurationMs": _float(audio.get("duration")) * 1000 if audio else None}


def _temp_path(output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".render-", suffix=".mp4", dir=str(output_path.parent))
    os.close(descriptor)
    return Path(temporary)


def _encoder_args():
    # concat uses a microsecond timebase. FFmpeg 7 may otherwise write an
    # incorrect last-frame duration / average FPS despite 30 fps input.
    # Set the output grid explicitly; retain strict frame-count validation.
    return ["-r", str(FPS), "-fps_mode", "cfr", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-movflags", "+faststart", "-map_metadata", "-1", "-metadata:s:v:0", "rotate=0"]


def _canonical(info):
    if not info["hasAudio"] or info["videoCodec"] != "h264" or info["audioCodec"] != "aac":
        raise ValueError("规范视频需要 H.264 画面和 AAC 声音。")
    if abs(info["fps"] - FPS) > 0.0001 or info["audioSampleRate"] != SAMPLE_RATE:
        raise ValueError("规范视频需要 30 fps 和 48 kHz 音轨。")
    if info["pixelFormat"] != "yuv420p":
        raise ValueError("规范视频需要浏览器支持的 yuv420p 色彩格式。")
    if info["totalFrames"] > MAX_SECONDS * FPS:
        raise ValueError("视频超过 180 秒，请先截短后再导入。")
    if abs(info["videoStartMs"]) > 1 or abs(info["audioStartMs"]) > 1:
        raise ValueError("规范视频音画起点不一致，请重新准备素材。")


def prepare_source(input_path, output_path, max_seconds=MAX_SECONDS) -> dict:
    if not 0 < max_seconds <= MAX_SECONDS:
        raise ValueError("视频时长上限应大于0且不超过180秒。")
    info = probe_media(input_path)
    if "mp4" not in info["formatName"].split(","):
        raise ValueError("当前支持 MP4 视频，请换一个文件。")
    video_end = info["videoStartMs"] + info["videoDurationMs"]
    audio_end = (info["audioStartMs"] or 0) + (info["audioDurationMs"] or 0)
    if max(video_end, audio_end) > max_seconds * 1000 + 1e-6:
        raise ValueError("视频超过 %s 秒，请先截短后再导入。" % max_seconds)
    if not info["hasAudio"]:
        raise ValueError("这段视频没有可用声音，无法演示口播剪辑。")
    if not all(info[key] for key in ("videoStartKnown", "audioStartKnown", "formatStartKnown")):
        raise ValueError("无法确定音画共同起点，请重新导出从零开始的 MP4 并校对字幕。")
    if abs(info["rotation"] / 90 - round(info["rotation"] / 90)) > 0.001:
        raise ValueError("视频旋转角度不受支持，请先转正画面后重新导入。")
    # Subtitle zero is the original player's zero. Reject unfamiliar origins;
    # supported delayed audio is padded against that SAME origin, never reset.
    if abs(info["formatStartMs"]) > 1 or abs(info["videoStartMs"]) > 1000 / FPS + 1:
        raise ValueError("视频起始时间偏移超出支持范围，请导出从零开始的 MP4 并校对字幕。")
    if info["audioStartMs"] < -1 or info["audioStartMs"] > 500:
        raise ValueError("声音起始偏移超出 500 毫秒支持范围，请先校正音画同步。")
    width, height = info["displayWidth"], info["displayHeight"]
    scale = min(1.0, 1280 / max(width, height), 720 / min(width, height))
    width, height = max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)
    # MP4's container duration may include AAC encoder padding. Video content,
    # rather than that padding, defines the canonical frame grid.
    if audio_end > video_end + 100:
        raise ValueError("声音明显长于画面，请先校正音画结束时间后再导入。")
    frames = max(1, int(math.ceil(video_end * FPS / 1000 - 1e-5)))
    seconds = frames / FPS
    temporary = _temp_path(output_path)
    try:
        arguments = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                     "-threads", "2", "-filter_threads", "2", "-filter_complex_threads", "2",
                     "-copyts", "-start_at_zero", "-i", str(input_path),
                     "-map", "0:%d" % info["videoStreamIndex"], "-map", "0:%d" % info["audioStreamIndex"], "-vf",
                     "fps=fps=30:start_time=0,scale=%d:%d,setsar=1,tpad=stop_mode=clone:stop_duration=1" % (width, height),
                     "-af", "aresample=48000:async=1:first_pts=0,apad", "-t", "%.9f" % seconds]
        _run(arguments + _encoder_args() + [str(temporary)], timeout=300)
        prepared = probe_media(temporary)
        _canonical(prepared)
        if abs(prepared["durationMs"] - seconds * 1000) > 100 or prepared["totalFrames"] != frames:
            raise ValueError("规范化后时长或帧数不一致，请重新导出原片。")
        os.replace(str(temporary), str(output_path))
        prepared["timelineOffsetMs"] = 0
        return prepared
    finally:
        temporary.unlink(missing_ok=True)


def render_spans(source_path, spans, output_path, progress_callback=None, timeout=240) -> dict:
    info = probe_media(source_path)
    _canonical(info)
    if not spans:
        raise ValueError("至少保留一段内容才能生成短片。")
    output_frames, previous_end = 0, 0
    graph, labels = [], []
    for index, span in enumerate(spans):
        start, end, output = (span.get(key) for key in ("sourceStartFrame", "sourceEndFrame", "outputStartFrame"))
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end, output)):
            raise ValueError("剪辑点必须使用整数帧。")
        if start < previous_end or end <= start or end > info["totalFrames"] or output != output_frames:
            raise ValueError("剪辑区间越界、顺序错误或输出起点不正确。")
        graph.append("[0:v:0]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[v%d]" % (start, end, index))
        graph.append("[0:a:0]atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS[a%d]" % (start * 1600, end * 1600, index))
        labels.append("[v%d][a%d]" % (index, index))
        output_frames += end - start
        previous_end = end
    graph.append("%sconcat=n=%d:v=1:a=1[outv][outa]" % ("".join(labels), len(spans)))
    temporary = _temp_path(output_path)
    try:
        if progress_callback:
            progress_callback("rendering", None)
        arguments = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "2",
                     "-filter_threads", "2", "-filter_complex_threads", "2", "-i", str(source_path),
                     "-filter_complex", ";".join(graph), "-map", "[outv]", "-map", "[outa]"]
        _run(arguments + _encoder_args() + [str(temporary)], timeout=timeout)
        if progress_callback:
            progress_callback("validating", None)
        rendered = probe_media(temporary)
        _canonical(rendered)
        if abs(rendered["durationMs"] - output_frames * 1000 / FPS) > 100:
            raise ValueError("成片实际时长与剪辑计划误差超过 100 毫秒，请重试。")
        if rendered["totalFrames"] != output_frames:
            raise ValueError("成片帧数与剪辑计划不一致，请重试。")
        os.replace(str(temporary), str(output_path))
        if progress_callback:
            progress_callback("done", 1.0)
        return rendered
    finally:
        temporary.unlink(missing_ok=True)


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_edit(source_path, spans, recordings, output_path, progress_callback=None, timeout=300):
    """V2 ordered EDL: source video and selected voice tracks share the frame clock."""
    source = probe_media(source_path)
    _canonical(source)
    if not spans:
        raise ValueError('至少保留一段内容才能生成短片。')
    temporary = _temp_path(output_path)
    try:
        args=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-threads','2',
              '-filter_threads','2','-filter_complex_threads','2','-i',str(source_path)]
        indexes={}
        for rid, path in recordings.items():
            indexes[rid]=len(indexes)+1
            args+=['-i',str(path)]
        graph, labels, frames=[],[],0
        for i,span in enumerate(spans):
            a,b,o=(span[k] for k in ['sourceStartFrame','sourceEndFrame','outputStartFrame'])
            rid=span.get('recordingId');audio_index=indexes[rid] if rid else 0
            if any(type(v) is not int for v in [a,b,o]) or not 0<=a<b or o!=frames:
                raise ValueError('剪辑区间或输出时间轴无效。')
            aa=span.get('audioStartFrame',a) if rid else a
            if type(aa) is not int or aa<0:raise ValueError('补录时间轴无效。')
            if rid and 'recordingVideoEndFrame' in span:
                va,vb=span['recordingVideoStartFrame'],span['recordingVideoEndFrame']
                if any(type(v) is not int for v in [va,vb]) or not 0<=va<vb<=source['totalFrames']:
                    raise ValueError('补录画面区间无效。')
                # Keep the original sentence picture; extend its last frame, never borrow the next sentence.
                start=min(va+aa,vb-1);end=min(vb,start+b-a)
                pad=max(0,b-a-(end-start))
                graph.append('[0:v:0]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop=%d,trim=end_frame=%d,setpts=N/(30*TB)[v%d]'%(start,end,pad,b-a,i))
            else:
                if b>source['totalFrames']:raise ValueError('剪辑画面区间无效。')
                graph.append('[0:v:0]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[v%d]'%(a,b,i))
            graph.append('[%d:a:0]aresample=48000,atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS[a%d]'%
                         (audio_index,aa*1600,(aa+b-a)*1600,i))
            labels.append('[v%d][a%d]'%(i,i));frames+=b-a
        graph.append(''.join(labels)+'concat=n=%d:v=1:a=1[outv][outa]'%len(spans))
        if progress_callback:progress_callback('rendering',None)
        _run(args+['-filter_complex',';'.join(graph),'-map','[outv]','-map','[outa]']+_encoder_args()+[str(temporary)],timeout)
        if progress_callback:progress_callback('validating',None)
        info=probe_media(temporary);_canonical(info)
        if info['totalFrames']!=frames or abs(info['durationMs']-frames/0.03)>100:
            raise ValueError('成片时长或帧数与剪辑清单不一致。')
        os.replace(str(temporary),str(output_path))
        return info
    finally:
        temporary.unlink(missing_ok=True)
