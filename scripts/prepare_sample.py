#!/usr/bin/env python3
"""Build the original Chinese sample using only installed, offline tools.

The eSpeak NG shared library is enough; its command-line program is optional.
Each block is synthesized separately and measured from actual WAV samples.
Never marks an unreviewed synthetic transcript as audio-verified.
"""
import argparse
import ctypes
import ctypes.util
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "fixtures" / "interview_intro_v1"
FPS = 30
AUDIO_RATE = 48000
WIDTH, HEIGHT = 1280, 720
PADDING_FRAMES = 8  # 267 ms of measured silence on each side of a cue.


def run(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Command failed: {}\n{}".format(args[0], result.stderr[-4000:]))
    return result.stdout


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OfflineMandarin:
    """Small synchronous binding to the public eSpeak-compatible C API."""

    def __init__(self, speed):
        name = ctypes.util.find_library("espeak-ng") or ctypes.util.find_library("espeak")
        if not name:
            raise RuntimeError("缺少本地 eSpeak NG 库。安装 libespeak-ng1 和 espeak-ng-data 后重试；脚本不会下载模型。")
        self.lib = ctypes.CDLL(name)
        self.lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        self.lib.espeak_Initialize.restype = ctypes.c_int
        # AUDIO_OUTPUT_SYNCHRONOUS returns PCM through the callback; no playback device.
        self.sample_rate = self.lib.espeak_Initialize(2, 0, None, 0)
        if self.sample_rate <= 0:
            raise RuntimeError("本地 eSpeak 语音数据初始化失败。")
        self.lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
        self.lib.espeak_SetVoiceByName.restype = ctypes.c_int
        if self.lib.espeak_SetVoiceByName(b"cmn"):
            raise RuntimeError("没有可用的 cmn 普通话语音数据。")
        self.lib.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        if self.lib.espeak_SetParameter(1, speed, 0):
            raise RuntimeError("无法设置 eSpeak 语速。")
        self.lib.espeak_Synth.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
            ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p,
        ]
        self.lib.espeak_Synth.restype = ctypes.c_int
        callback_type = ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
        self.chunks = []

        @callback_type
        def callback(samples, count, _events):
            if samples and count:
                self.chunks.append(ctypes.string_at(samples, count * 2))
            return 0

        self.callback = callback  # Keep the C callback alive for the entire engine lifetime.
        self.lib.espeak_SetSynthCallback.argtypes = [callback_type]
        self.lib.espeak_SetSynthCallback(callback)
        self.lib.espeak_Info.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        self.lib.espeak_Info.restype = ctypes.c_char_p
        data_path = ctypes.c_char_p()
        self.version = self.lib.espeak_Info(ctypes.byref(data_path)).decode("utf-8")
        self.library_name = name

    def synthesize(self, text, output):
        self.chunks = []
        encoded = text.encode("utf-8")
        # espeakCHARS_UTF8=1. No SSML, phoneme markup, voice cloning, or remote calls.
        code = self.lib.espeak_Synth(encoded, len(encoded) + 1, 0, 1, 0, 1, None, None)
        self.lib.espeak_Synchronize()
        if code or not self.chunks:
            raise RuntimeError("中文语音合成失败：{}".format(output.name))
        pcm = b"".join(self.chunks)
        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(self.sample_rate)
            audio.writeframes(pcm)
        return len(pcm) // 2

    def close(self):
        self.lib.espeak_Terminate()


def find_font():
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"),
    ]
    for font in candidates:
        if font.exists():
            return font
    raise RuntimeError("需要本地中文字体 Noto Sans CJK（fonts-noto-cjk）。")


def wrap_text(text, font, width, draw):
    lines, line = [], ""
    for char in text:
        candidate = line + char
        if line and draw.textbbox((0, 0), candidate, font=font)[2] > width:
            # Prefer a nearby clause ending; avoid leaving punctuation at line start.
            stops = [i + 1 for i, value in enumerate(line)
                     if value in "，。；：！？" and i >= len(line) * 0.55]
            if stops:
                split = stops[-1]
                lines.append(line[:split])
                line = line[split:] + char
            elif char in "，。；：！？、）】”’":
                lines.append(line[:-1])
                line = line[-1] + char
            else:
                lines.append(line)
                line = char
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def draw_card(block, index, font_path, output):
    image = Image.new("RGB", (WIDTH, HEIGHT), "#F3F7F8")
    draw = ImageDraw.Draw(image)
    font = lambda size: ImageFont.truetype(str(font_path), size)
    draw.rounded_rectangle((56, 48, 1224, 612), radius=24, fill="#FFFFFF")
    draw.rounded_rectangle((88, 80, 258, 122), radius=21, fill="#E1F1ED")
    draw.text((108, 85), "面试项目介绍", font=font(21), fill="#286A5D")
    draw.text((1014, 84), "{}  /  13".format(block["id"].upper()), font=font(22), fill="#657889")
    draw.text((88, 160), block["title"], font=font(44), fill="#213545")
    draw.rectangle((88, 238, 1192, 240), fill="#E7EDF0")
    body_font = font(35)
    lines = wrap_text(block["text"], body_font, 1000, draw)
    if len(lines) > 5:
        raise RuntimeError("文字卡超出五行，请调整排版：" + block["id"])
    for line_index, line in enumerate(lines):
        draw.text((88, 278 + 56 * line_index), line, font=body_font, fill="#304959")
    draw.text((88, 556), "原创演示叙述 · 非真实个人经历", font=font(21), fill="#7B8B96")
    draw.text((80, 638), "合成旁白＋示例画面", font=font(23), fill="#526D79")
    draw.text((800, 640), "源视频时间", font=font(20), fill="#7B8B96")
    # Each card also carries a distinct position in the 13-block sequence.
    for number in range(13):
        x = 416 + number * 25
        draw.rounded_rectangle((x, 650, x + 16, 656), radius=3,
                               fill="#398F7D" if number == index else "#D6E4E7")
    image.save(output)


def timestamp(milliseconds):
    whole = int(round(milliseconds))
    hours, whole = divmod(whole, 3600000)
    minutes, whole = divmod(whole, 60000)
    seconds, millis = divmod(whole, 1000)
    return "{:02}:{:02}:{:02},{:03}".format(hours, minutes, seconds, millis)


def build(output, script_path, speed, work):
    script = json.loads(script_path.read_text(encoding="utf-8"))
    blocks = script["blocks"]
    if [block["id"] for block in blocks] != ["s{:02}".format(i) for i in range(1, 14)]:
        raise ValueError("样例必须保留 s01 至 s13 的完整语义块。")
    font_path = find_font()
    engine = OfflineMandarin(speed)
    timings, pcm_parts, cards = [], [], []
    total_frames = 0
    samples_per_frame = AUDIO_RATE // FPS
    try:
        for index, block in enumerate(blocks):
            raw_path = work / (block["id"] + "_original.wav")
            raw_samples = engine.synthesize(block["text"], raw_path)
            normalized = work / (block["id"] + ".wav")
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                 "-i", raw_path, "-ar", AUDIO_RATE, "-ac", 1, "-c:a", "pcm_s16le", normalized])
            with wave.open(str(normalized), "rb") as wav:
                measured_samples = wav.getnframes()
                assert wav.getframerate() == AUDIO_RATE and wav.getsampwidth() == 2
                pcm = wav.readframes(measured_samples)
            if measured_samples <= 0 or not any(pcm):
                raise RuntimeError("合成音轨为空：" + block["id"])
            speech_frames = math.ceil(measured_samples / samples_per_frame)
            segment_frames = speech_frames + PADDING_FRAMES * 2
            leading = PADDING_FRAMES * samples_per_frame
            trailing = segment_frames * samples_per_frame - leading - measured_samples
            pcm_parts.append(b"\0" * (leading * 2) + pcm + b"\0" * (trailing * 2))
            cue_start = total_frames + PADDING_FRAMES
            cue_end = cue_start + speech_frames
            card = work / (block["id"] + ".png")
            draw_card(block, index, font_path, card)
            # A one-frame MP4 gives concat an exact 30 fps time base on older
            # FFmpeg too. Direct PNG concat defaults to 25 fps and can move cuts.
            card_video = work / (block["id"] + "_card.mp4")
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                 "-framerate", FPS, "-i", card, "-frames:v", 1, "-c:v", "libx264",
                 "-crf", 18, "-pix_fmt", "yuv420p", "-threads", 1, card_video])
            cards.append((card_video, segment_frames))
            timing = {
                "id": block["id"], "text": block["text"], "purpose": block["purpose"],
                "clipStartFrame": total_frames, "clipEndFrame": total_frames + segment_frames,
                # SRT stores integer milliseconds. Round inward so ceil(end)/floor(start)
                # in the shared timeline recovers exactly the original frame gap.
                "cueStartMs": math.ceil(cue_start * 1000 / FPS),
                "cueEndMs": math.floor(cue_end * 1000 / FPS),
                "ttsOriginalSampleRate": engine.sample_rate, "ttsOriginalSamples": raw_samples,
                "ttsOriginalDurationMs": raw_samples * 1000 / engine.sample_rate,
                "normalizedAudioSamples": measured_samples,
                "normalizedAudioDurationMs": measured_samples * 1000 / AUDIO_RATE,
                "segmentDurationMs": segment_frames * 1000 / FPS,
                "wavSha256": sha256(normalized),
            }
            timings.append(timing)
            total_frames += segment_frames
            print("{}: TTS {:.3f}s, segment {:.3f}s".format(
                block["id"], measured_samples / AUDIO_RATE, segment_frames / FPS), flush=True)
        engine_version = engine.version
        library_name = engine.library_name
    finally:
        engine.close()
    duration = total_frames / FPS
    if duration > 180:
        raise ValueError("实际合成时长 {:.3f} 秒超过 180 秒；请调整普通语速后重新生成。".format(duration))
    narration = work / "narration.wav"
    with wave.open(str(narration), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(AUDIO_RATE)
        wav.writeframes(b"".join(pcm_parts))
    # Paths are generated internally in a temporary directory, never from uploaded names.
    concat_file = work / "cards.ffconcat"
    concat_lines = ["ffconcat version 1.0"]
    for card, count in cards:
        concat_lines.extend(["file '{}'".format(card.name),
                             "duration {:.9f}".format(count / FPS)])
    concat_lines.append("file '{}'".format(cards[-1][0].name))
    concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    mono_font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
    if not mono_font.exists():
        mono_font = font_path
    filters = (
        "fps=30,drawtext=fontfile={font}:text='%{{pts\\:hms}}':x=968:y=642:"
        "fontsize=23:fontcolor=0x526D79,"
        "drawbox=x=80:y=688:w=1120:h=3:color=0xD6E4E7:t=fill,"
        "drawtext=fontfile={font}:text='|':x='80+1104*t/{duration}':y=668:"
        "fontsize=30:fontcolor=0x398F7D"
    ).format(font=mono_font, duration=duration)
    target = output / "canonical.tmp.mp4"
    silent_video = work / "card_timeline.mp4"
    # Encoding video and audio together with a sparse still-frame input and
    # -frames:v can stop audio packets early on FFmpeg 4.2. Encode and mux in
    # separate steps so the entire final spoken sentence is preserved.
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
         "-f", "concat", "-safe", 0, "-i", concat_file,
         "-map", "0:v:0", "-vf", filters,
         "-frames:v", total_frames, "-t", "{:.9f}".format(duration),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", 24, "-pix_fmt", "yuv420p",
         "-threads", 2, "-an", silent_video])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
         "-i", silent_video, "-i", narration, "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-ar", AUDIO_RATE,
         "-t", "{:.9f}".format(duration),
         "-movflags", "+faststart", "-metadata", "title=" + script["title"], target])
    probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", target]))
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
    actual_frames = int(video["nb_frames"])
    if actual_frames != total_frames or video["avg_frame_rate"] != "30/1":
        raise RuntimeError("规范源帧数或帧率与实测音轨不一致。")
    if abs(float(probe["format"]["duration"]) - duration) > 0.1:
        raise RuntimeError("规范源时长与音轨不一致。")
    if int(audio["sample_rate"]) != AUDIO_RATE:
        raise RuntimeError("规范源音频采样率不正确。")
    if abs(float(audio["duration"]) - duration) > 0.1:
        raise RuntimeError("规范源音轨时长与实测拼接WAV不一致，可能出现尾音截断。")
    # Decode the complete output once to catch a broken media file before publication.
    run(["ffmpeg", "-v", "error", "-nostdin", "-i", target, "-f", "null", "-"])
    canonical = output / "canonical.mp4"
    target.replace(canonical)
    srt = output / "sample.srt"
    srt.write_text("\n\n".join("{}\n{} --> {}\n{}".format(
        index + 1, timestamp(timing["cueStartMs"]), timestamp(timing["cueEndMs"]), timing["text"])
        for index, timing in enumerate(timings)) + "\n", encoding="utf-8")
    # Self-contained output when --output is different from the checked-in sample folder.
    local_script = output / "script.json"
    if local_script.resolve() != script_path.resolve():
        shutil.copyfile(script_path, local_script)
    source_hash, transcript_hash = sha256(canonical), sha256(srt)
    manifest = {
        "schemaVersion": 1, "id": script["sampleId"], "sampleId": script["sampleId"],
        "title": script["title"], "description": script["description"],
        "origin": "synthetic_narration", "label": "合成旁白＋示例画面",
        "licenseNote": "原创脚本与代码绘制文字卡；本地 eSpeak NG cmn 普通合成声音，无声音克隆。引擎为 GPL-3.0-or-later，Noto CJK 字体为 SIL OFL 1.1；仓库不捆绑引擎或字体二进制。",
        "videoFile": "canonical.mp4", "sourceFile": "canonical.mp4", "subtitleFile": "sample.srt",
        "transcriptFile": "sample.srt", "scriptFile": "script.json",
        "sourceSha256": source_hash, "transcriptSha256": transcript_hash,
        "scriptSha256": sha256(local_script), "durationMs": duration * 1000, "totalFrames": total_frames,
        "source": {"path": "canonical.mp4", "sha256": source_hash, "totalFrames": total_frames,
                   "durationMs": duration * 1000, "width": WIDTH, "height": HEIGHT, "fps": FPS,
                   "audioSampleRate": AUDIO_RATE, "videoCodec": video["codec_name"], "audioCodec": audio["codec_name"],
                   "videoDurationMs": float(video["duration"]) * 1000,
                   "audioDurationMs": float(audio["duration"]) * 1000},
        "mediaVerification": {"completeDecodePassed": True, "frameCountMatches": True,
                              "audioDurationMatchesMeasuredWav": True, "maximumDurationErrorMs": 100},
        "transcriptVerified": False, "ttsInputMatchesSrt": True,
        "transcriptVerification": {"status": "pending_audio_review", "humanListeningCompleted": False,
            "timingMethod": "每段 WAV 实际采样数测量；重采样后按30fps补齐，前后各8帧静音；非字数估算。",
            "textMethod": "同一 script.json 字符串逐字用于 TTS 输入与 SRT；尚未逐字听审合成输出。"},
        "recommendedLockedIds": ["s03", "s04", "s05"], "preparedSuggestionSource": "rules",
        "preparedSuggestionBinding": {"sourceSha256": source_hash, "transcriptSha256": transcript_hash},
        "recommendedDeletionOrder": ["s06", "s09", "s08", "s13", "s02", "s07", "s11"],
        "sampleSources": [
            {"kind": "script", "name": "交接书第5.2章原创13段脚本", "path": "script.json",
             "note": "完整保留每行语义；s05建议与适用范围共同组成一个cue。内容是演示叙述。"},
            {"kind": "audio", "name": "eSpeak NG cmn (Chinese Mandarin)", "version": engine_version,
             "library": library_name, "voice": "cmn", "rate": speed, "networkUsed": False,
             "license": "GPL-3.0-or-later (engine)",
             "licenseEvidence": "/usr/share/doc/libespeak-ng1/copyright",
             "upstream": "https://github.com/espeak-ng/espeak-ng",
             "note": "本机已安装库和语言数据生成；普通合成声音，机械音色，未经真人自然度验证。"},
            {"kind": "visual", "name": "原创中性中文文字卡与动态源时间", "tool": "Pillow + FFmpeg",
             "note": "无外部照片、人物肖像、私人视频或生成式图片。"},
            {"kind": "font", "name": "Noto Sans CJK", "license": "SIL OFL 1.1",
             "licenseEvidence": "/usr/share/doc/fonts-noto-cjk/copyright", "renderedFont": font_path.name}
        ],
        "limitations": ["transcriptVerified=false：尚未进行人工逐字听审；TTS输入一致不能代替声音审校。",
                        "合成样例支持剪辑、恢复、字幕映射与导出验证；真人口播切口自然度仍需真实素材验证。"],
        "segmentTimings": timings,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "durationMs": duration * 1000, "totalFrames": total_frames,
                      "sourceSha256": source_hash, "transcriptSha256": transcript_hash}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--script", type=Path, default=DEFAULT_OUTPUT / "script.json")
    parser.add_argument("--rate", type=int, default=180, help="eSpeak rate; default 180, no audio time-stretch")
    parser.add_argument("--keep-work", action="store_true", help="保留逐块 WAV、卡片与合并 WAV 到 _work/")
    args = parser.parse_args()
    if not 140 <= args.rate <= 220:
        parser.error("--rate 应在 140 到 220 之间，避免极端语速。")
    for command in ["ffmpeg", "ffprobe"]:
        if not shutil.which(command):
            parser.error("需要本地 " + command)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.keep_work:
        work = args.output / "_work"
        work.mkdir(exist_ok=True)
        build(args.output, args.script.resolve(), args.rate, work)
    else:
        with tempfile.TemporaryDirectory(prefix="koubo_sample_") as directory:
            build(args.output, args.script.resolve(), args.rate, Path(directory))


if __name__ == "__main__":
    main()
