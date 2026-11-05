#!/usr/bin/env python3
"""Generate and verify an original six-second A/B/C engineering fixture."""
import argparse
from array import array
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.media import prepare_source, render_spans, sha256_file
from backend.app.timeline import parse_srt, build_blocks, build_spans, map_cues, write_srt, write_vtt

SOURCE_SRT = """1
00:00:00,100 --> 00:00:01,900
A：红色画面，440 Hz。

2
00:00:02,100 --> 00:00:03,900
B：绿色画面，660 Hz。

3
00:00:04,100 --> 00:00:05,900
C：蓝色画面，880 Hz。
"""


def command(arguments):
    result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-3000:])
    return result.stdout


def frequency_at(path, at):
    raw = command(["ffmpeg", "-v", "error", "-threads", "2", "-ss", str(at), "-i", str(path),
                   "-t", "0.4", "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"])
    samples = array("h", raw)
    if sys.byteorder != "little":
        samples.byteswap()
    crossings = sum(left <= 0 < right for left, right in zip(samples, samples[1:]))
    return round(crossings / (len(samples) / 48000), 2)


def color_at(path, at):
    raw = command(["ffmpeg", "-v", "error", "-threads", "2", "-filter_threads", "2", "-ss", str(at),
                   "-i", str(path), "-frames:v", "1", "-vf", "crop=2:2:20:20,scale=1:1",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    if len(raw) != 3:
        raise RuntimeError("无法读取工程测试帧")
    return list(raw)


def all_frame_colors(path):
    raw = command(["ffmpeg", "-v", "error", "-threads", "2", "-filter_threads", "2", "-i", str(path),
                   "-vf", "crop=2:2:20:20,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    colors = [list(raw[index:index + 3]) for index in range(0, len(raw), 3)]
    return [color.index(max(color)) for color in colors]


def generate(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    raw, source, cut, restored = [destination / name for name in
                                ("input_abc.mp4", "source_abc.mp4", "cut_ac.mp4", "restored_abc.mp4")]
    draw = ("drawbox=color=0x2C9F55:t=fill:enable='gte(t,2)*lt(t,4)',"
            "drawbox=color=0x345EC4:t=fill:enable='gte(t,4)',"
            "drawtext=text='A  |  440 Hz':fontsize=48:fontcolor=white:x=(w-tw)/2:y=(h-th)/2:enable='lt(t,2)',"
            "drawtext=text='B  |  660 Hz':fontsize=48:fontcolor=white:x=(w-tw)/2:y=(h-th)/2:enable='gte(t,2)*lt(t,4)',"
            "drawtext=text='C  |  880 Hz':fontsize=48:fontcolor=white:x=(w-tw)/2:y=(h-th)/2:enable='gte(t,4)'")
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "2", "-filter_threads", "2",
             "-filter_complex_threads", "2", "-f", "lavfi", "-i", "color=c=0xC43A3A:s=640x360:r=30:d=6",
             "-f", "lavfi", "-i", "aevalsrc=0.12*sin(2*PI*if(lt(t\\,2)\\,440\\,if(lt(t\\,4)\\,660\\,880))*t):s=48000:d=6",
             "-vf", draw, "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "21",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart", str(raw)])
    source_info = prepare_source(raw, source)
    (destination / "source_abc.srt").write_text(SOURCE_SRT, encoding="utf-8")
    cues = parse_srt(SOURCE_SRT, source_info["durationMs"])
    blocks = build_blocks(cues, source_info["totalFrames"])
    spans = build_spans(blocks, ["s01", "s03"])
    cut_info = render_spans(source, spans, cut)
    mapped = map_cues(cues, spans)
    (destination / "cut_ac.srt").write_text(write_srt(mapped), encoding="utf-8")
    (destination / "cut_ac.vtt").write_text(write_vtt(mapped), encoding="utf-8")
    restore_spans = build_spans(blocks, [block["id"] for block in blocks])
    restored_info = render_spans(source, restore_spans, restored)
    (destination / "restored_abc.srt").write_text(write_srt(map_cues(cues, restore_spans)), encoding="utf-8")
    source_samples = [{"atSeconds": at, "rgb": color_at(source, at), "frequencyHz": frequency_at(source, at)} for at in (0.5, 2.5, 4.5)]
    cut_samples = [{"atSeconds": at, "rgb": color_at(cut, at), "frequencyHz": frequency_at(cut, at)} for at in (0.5, 1.5, 2.5, 3.5)]
    assert source_info["totalFrames"] == 180 and cut_info["totalFrames"] == 120
    assert restored_info["totalFrames"] == 180
    assert [cue["id"] for cue in mapped] == ["c001", "c003"]
    assert mapped[1]["startMs"] == 2100 and mapped[1]["endMs"] == 3900
    for sample, expected in zip(source_samples, (440, 660, 880)):
        assert abs(sample["frequencyHz"] - expected) <= 5
    for sample, expected in zip(cut_samples, (440, 440, 880, 880)):
        assert abs(sample["frequencyHz"] - expected) <= 5
        rgb = sample["rgb"]
        assert rgb[0 if expected == 440 else 2] == max(rgb)
    source_colors, cut_colors = all_frame_colors(source), all_frame_colors(cut)
    assert source_colors == [0] * 60 + [1] * 60 + [2] * 60
    assert cut_colors == [0] * 60 + [2] * 60
    contact_sheet = destination / "contact_sheet.png"
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "2", "-filter_complex_threads", "2",
             "-i", str(source), "-i", str(cut), "-filter_complex",
             "[0:v]fps=1/2,scale=320:180,tile=3x1[top];[1:v]fps=1/2,scale=320:180,tile=3x1[bottom];[top][bottom]vstack[out]",
             "-map", "[out]", "-frames:v", "1", "-threads", "2", str(contact_sheet)])
    report = {"classification": "原创色卡与正弦音工程测试，不是真人口播", "source": source_info,
              "cut": cut_info, "restored": restored_info, "blocks": blocks, "spans": spans,
              "mappedCues": mapped, "sourceDecodedSamples": source_samples, "cutDecodedSamples": cut_samples,
              "checks": {"sourceFrames": 180, "cutFrames": 120, "restoredFrames": 180,
                         "colorOrder": "A then C", "audioOrderHz": [440, 880], "removedCue": "c002",
                         "allSourceFramesColorVerified": len(source_colors),
                         "allCutFramesColorVerified": len(cut_colors), "cutFramesContainingB": 0,
                         "cCueShiftMs": -2000, "automatedDecodePassed": True,
                         "humanListeningCompleted": False},
              "sha256": {path.name: sha256_file(path) for path in (source, cut, restored)}}
    (destination / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "engineering_fixture"))
    arguments = parser.parse_args()
    report = generate(arguments.output_dir)
    print(json.dumps({"outputDir": arguments.output_dir, "checks": report["checks"],
                      "durationsMs": {key: report[key]["durationMs"] for key in ("source", "cut", "restored")}}, ensure_ascii=False, indent=2))
