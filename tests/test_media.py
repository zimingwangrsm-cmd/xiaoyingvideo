from array import array
from pathlib import Path
import subprocess

import pytest

from backend.app import media
from scripts.prepare_test_media import generate, command


@pytest.fixture(scope="module")
def engineering(tmp_path_factory):
    destination = tmp_path_factory.mktemp("engineering")
    return destination, generate(destination)


def test_real_abc_cut_restore_pixels_tones_and_captions(engineering):
    destination, report = engineering
    assert report["checks"]["automatedDecodePassed"]
    assert report["source"]["totalFrames"] == 180
    assert report["cut"]["totalFrames"] == 120
    assert abs(report["cut"]["durationMs"] - 4000) <= 100
    assert report["restored"]["totalFrames"] == 180
    assert "B：" not in (destination / "cut_ac.srt").read_text()
    assert "B：" in (destination / "restored_abc.srt").read_text()


def test_render_phases_and_frame_exact_cut(engineering, tmp_path):
    source = engineering[0] / "source_abc.mp4"
    phases = []
    result = media.render_spans(source, [{"sourceStartFrame": 31, "sourceEndFrame": 61, "outputStartFrame": 0}],
                                tmp_path / "result.mp4", lambda phase, progress: phases.append((phase, progress)))
    assert result["totalFrames"] == 30
    assert abs(result["durationMs"] - 1000) <= 100
    assert phases == [("rendering", None), ("validating", None), ("done", 1.0)]


def test_failed_validation_does_not_replace_existing_output(engineering, tmp_path, monkeypatch):
    output = tmp_path / "published.mp4"
    output.write_bytes(b"previous approved artifact")
    real_probe = media.probe_media
    def corrupt_probe(path):
        result = real_probe(path)
        if Path(path).name.startswith(".render-"):
            result["durationMs"] += 101
        return result
    monkeypatch.setattr(media, "probe_media", corrupt_probe)
    with pytest.raises(ValueError, match="超过 100"):
        media.render_spans(engineering[0] / "source_abc.mp4", engineering[1]["spans"], output)
    assert output.read_bytes() == b"previous approved artifact"
    assert not list(tmp_path.glob(".render-*"))


def test_invalid_edl_is_rejected_before_encoding(engineering, tmp_path):
    source = engineering[0] / "source_abc.mp4"
    with pytest.raises(ValueError, match="至少保留"):
        media.render_spans(source, [], tmp_path / "bad.mp4")
    with pytest.raises(ValueError, match="越界"):
        media.render_spans(source, [{"sourceStartFrame": 0, "sourceEndFrame": 181, "outputStartFrame": 0}], tmp_path / "bad.mp4")
    with pytest.raises(ValueError, match="整数帧"):
        media.render_spans(source, [{"sourceStartFrame": 0.1, "sourceEndFrame": 100, "outputStartFrame": 0}], tmp_path / "bad.mp4")


def _offset_fixture(path, offset=0.2):
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "2", "-filter_threads", "2",
             "-f", "lavfi", "-i", "color=c=red:s=160x90:r=30:d=2", "-itsoffset", str(offset),
             "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1.7",
             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", str(path)])


def _rms_window(path, at, duration):
    raw = command(["ffmpeg", "-v", "error", "-threads", "2", "-ss", str(at), "-i", str(path),
                   "-t", str(duration), "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"])
    samples = array("h", raw)
    return (sum(value * value for value in samples) / max(len(samples), 1)) ** 0.5


def test_known_delayed_audio_preserves_common_zero_instead_of_shifting_speech(tmp_path):
    source, prepared = tmp_path / "delayed.mp4", tmp_path / "prepared.mp4"
    _offset_fixture(source)
    original = media.probe_media(source)
    assert 150 < original["audioStartMs"] < 220
    result = media.prepare_source(source, prepared)
    assert result["audioStartMs"] == 0
    assert result["videoStartMs"] == 0
    assert result["totalFrames"] == 60
    assert _rms_window(prepared, 0.02, 0.10) < 20
    assert _rms_window(prepared, 0.25, 0.10) > 1000


def test_unknown_offset_missing_audio_and_long_source_are_rejected(engineering, tmp_path, monkeypatch):
    original = media.probe_media(engineering[0] / "source_abc.mp4")
    for changes, message in [({"hasAudio": False}, "没有可用声音"),
                             ({"audioStartKnown": False}, "无法确定音画共同起点"),
                             ({"audioStartMs": 501, "audioDurationMs": 5400}, "500 毫秒"),
                             ({"videoStartMs": 1000, "formatStartMs": 1000}, "起始时间偏移"),
                             ({"videoDurationMs": 181000}, "超过 180 秒")]:
        monkeypatch.setattr(media, "probe_media", lambda path, changes=changes: dict(original, **changes))
        with pytest.raises(ValueError, match=message):
            media.prepare_source("input.mp4", tmp_path / "invalid.mp4")
    assert not (tmp_path / "invalid.mp4").exists()


def test_real_missing_audio_is_rejected(engineering, tmp_path):
    silent = tmp_path / "silent.mp4"
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(engineering[0] / "source_abc.mp4"),
             "-an", "-c:v", "copy", str(silent)])
    with pytest.raises(ValueError, match="没有可用声音"):
        media.prepare_source(silent, tmp_path / "invalid.mp4")


def test_timeout_cleans_temporary_output(engineering, tmp_path, monkeypatch):
    source = engineering[0] / "source_abc.mp4"
    real_run = subprocess.run
    def timeout_render(arguments, **kwargs):
        if arguments[0] == "ffmpeg":
            raise subprocess.TimeoutExpired(arguments, 1)
        return real_run(arguments, **kwargs)
    monkeypatch.setattr(media.subprocess, "run", timeout_render)
    with pytest.raises(ValueError, match="超时"):
        media.render_spans(source, engineering[1]["spans"], tmp_path / "timeout.mp4")
    assert not list(tmp_path.iterdir())


def test_rotation_is_applied_and_small_portrait_is_not_enlarged(engineering, tmp_path):
    rotated = tmp_path / "rotated.mp4"
    # FFmpeg 7 no longer writes display matrices via the legacy rotate tag.
    help_text = command(["ffmpeg", "-hide_banner", "-h", "full"]).decode("utf-8", "replace")
    rotation_input = ["-display_rotation:v:0", "90"] if "-display_rotation" in help_text else []
    rotation_output = [] if rotation_input else ["-metadata:s:v:0", "rotate=90"]
    command(["ffmpeg", "-v", "error", "-nostdin", "-y"] + rotation_input +
            ["-i", str(engineering[0] / "source_abc.mp4"), "-c", "copy"] + rotation_output + [str(rotated)])
    original = media.probe_media(rotated)
    assert abs(original["rotation"]) == 90
    result = media.prepare_source(rotated, tmp_path / "portrait.mp4")
    assert (result["width"], result["height"]) == (360, 640)
    assert result["rotation"] == 0
    assert result["totalFrames"] == 180


def test_anamorphic_pixels_preserve_display_aspect(tmp_path):
    source = tmp_path / "anamorphic.mp4"
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "2", "-filter_threads", "2",
             "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=30:d=1", "-f", "lavfi", "-i",
             "sine=frequency=440:sample_rate=48000:duration=1", "-vf", "setsar=2/1",
             "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)])
    result = media.prepare_source(source, tmp_path / "square_pixels.mp4")
    assert (result["width"], result["height"]) == (320, 90)


def test_real_181_second_input_is_rejected_before_preparation(tmp_path):
    source = tmp_path / "too_long.mp4"
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "2", "-filter_threads", "2",
             "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1:d=181", "-f", "lavfi", "-i",
             "anullsrc=channel_layout=mono:sample_rate=48000", "-t", "181", "-c:v", "libx264",
             "-threads", "2", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)])
    assert media.probe_media(source)["videoDurationMs"] == 181000
    with pytest.raises(ValueError, match="超过 180 秒"):
        media.prepare_source(source, tmp_path / "invalid.mp4")
    assert not (tmp_path / "invalid.mp4").exists()



def test_concat_output_has_exact_constant_frame_rate(engineering, tmp_path):
    source, fixture = engineering
    for name, spans in [("cut", fixture["spans"]), ("full", [{"sourceStartFrame": 0, "sourceEndFrame": 180, "outputStartFrame": 0}])]:
        out = tmp_path / (name + ".mp4")
        info = media.render_spans(source / "source_abc.mp4", spans, out)
        expected = sum(s["sourceEndFrame"] - s["sourceStartFrame"] for s in spans)
        assert info["fps"] == 30
        assert info["totalFrames"] == expected
        assert abs(info["videoDurationMs"] - expected * 1000 / 30) < 1
