import random

import pytest

from backend.app.timeline import build_blocks, build_spans, duration_ms, map_cues, parse_srt, write_srt, write_vtt
from scripts.prepare_test_media import SOURCE_SRT


def test_full_coverage_delete_restore_and_shared_caption_mapping():
    cues = parse_srt("\ufeff" + SOURCE_SRT.replace("\n", "\r\n"), 6000)
    blocks = build_blocks(cues, 180)
    assert [(block["clipStartFrame"], block["clipEndFrame"]) for block in blocks] == [(0, 60), (60, 120), (120, 180)]
    full = build_spans(blocks, ["s03", "s01", "s02"])
    assert full == [{"sourceStartFrame": 0, "sourceEndFrame": 180, "outputStartFrame": 0,
                     "blockIds": ["s01", "s02", "s03"]}]
    assert duration_ms(full) == 6000
    cut = build_spans(blocks, ["s03", "s01"])
    assert duration_ms(cut) == 4000
    mapped = map_cues(cues, cut)
    assert [cue["id"] for cue in mapped] == ["c001", "c003"]
    assert mapped[1]["startMs"] == 2100
    assert mapped[1]["text"] == cues[2]["text"]
    assert "B：" not in write_srt(mapped)
    assert "00:00:02,100 --> 00:00:03,900" in write_srt(mapped)
    assert "00:00:02.100 --> 00:00:03.900" in write_vtt(mapped)
    assert len(map_cues(cues, full)) == 3


@pytest.mark.parametrize("text,match", [
    ("", "没有有效"),
    ("1\n00:00:01,000 --> 00:00:00,000\n错。", "结束时间"),
    ("1\n-00:00:01,000 --> 00:00:02,000\n错。", "时间码"),
    ("1\n00:00:00,000 --> 00:00:07,000\n错。", "超过视频"),
    ("1\n00:00:00,000 --> 00:00:03,000\n前。\n\n2\n00:00:02,000 --> 00:00:04,000\n后。", "第 2 条.*重叠"),
    ("1\n00:80:00,000 --> 00:81:00,000\n错。", "时间码"),
])
def test_srt_rejects_invalid_input_with_specific_feedback(text, match):
    with pytest.raises(ValueError, match=match):
        parse_srt(text, 6000)


def test_multiline_cue_is_atomic_and_fragments_merge_until_sentence_end():
    cues = parse_srt("1\n00:00:00,100 --> 00:00:01,500\n这是\n多行字幕\n\n"
                     "2\n00:00:01,600 --> 00:00:03,000\n完整的一句。\n\n"
                     "3\n00:00:03,500 --> 00:00:05,900\n第二句。还有一句。", 6000)
    blocks = build_blocks(cues, 180)
    assert len(blocks) == 2
    assert blocks[0]["cueIds"] == ["c001", "c002"]
    assert blocks[1]["cueIds"] == ["c003"]
    assert "这是\n多行字幕" in blocks[0]["text"]


def test_no_legal_frame_gap_merges_adjacent_sentences():
    cues = [{"id": "c001", "startMs": 0, "endMs": 1001, "text": "前句。"},
            {"id": "c002", "startMs": 1002, "endMs": 1900, "text": "后句。"},
            {"id": "c003", "startMs": 2100, "endMs": 2900, "text": "独立。"}]
    blocks = build_blocks(cues, 90)
    assert [block["cueIds"] for block in blocks] == [["c001", "c002"], ["c003"]]
    assert blocks[0]["clipEndFrame"] == blocks[1]["clipStartFrame"] == 60


def test_frame_boundaries_cover_source_and_never_split_a_cue():
    rng = random.Random(7)
    for _ in range(50):
        cues, cursor = [], 10
        for index in range(20):
            start = cursor + rng.randint(0, 100)
            end = start + rng.randint(1, 1000)
            cues.append({"id": "c%d" % index, "startMs": start, "endMs": end, "text": "完整句。"})
            cursor = end
        total_frames = (cursor * 30 + 999) // 1000 + 3
        blocks = build_blocks(cues, total_frames)
        assert blocks[0]["clipStartFrame"] == 0
        assert blocks[-1]["clipEndFrame"] == total_frames
        assert sum(block["clipEndFrame"] - block["clipStartFrame"] for block in blocks) == total_frames
        for block in blocks:
            for cue in [cue for cue in cues if cue["id"] in block["cueIds"]]:
                assert cue["startMs"] >= block["clipStartFrame"] * 1000 / 30 - 1e-7
                assert cue["endMs"] <= block["clipEndFrame"] * 1000 / 30 + 1e-7


def test_empty_unknown_and_split_cue_are_rejected():
    cues = parse_srt(SOURCE_SRT, 6000)
    blocks = build_blocks(cues, 180)
    with pytest.raises(ValueError, match="至少保留"):
        build_spans(blocks, [])
    with pytest.raises(ValueError, match="不存在"):
        build_spans(blocks, ["s99"])
    with pytest.raises(ValueError, match="被切口拆开"):
        map_cues(cues, [{"sourceStartFrame": 15, "sourceEndFrame": 60, "outputStartFrame": 0}])


def test_no_punctuation_gets_actionable_error():
    cues = [{"id": "a", "startMs": 0, "endMs": 1000, "text": "没有标点"},
            {"id": "b", "startMs": 2000, "endMs": 3000, "text": "需要校正"}]
    with pytest.raises(ValueError, match="按完整句校正"):
        build_blocks(cues, 90)


def test_only_final_serialization_rounds_fractional_frame_time():
    cue = {"id": "c1", "startMs": 35, "endMs": 55, "text": "一句。"}
    spans = [{"sourceStartFrame": 1, "sourceEndFrame": 2, "outputStartFrame": 0}]
    mapped = map_cues([cue], spans)
    assert mapped[0]["startMs"] == pytest.approx(5 / 3)
    assert "00:00:00,002 --> 00:00:00,022" in write_srt(mapped)
