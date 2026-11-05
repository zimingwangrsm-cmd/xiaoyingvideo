"""The single, frame-based edit timeline shared by rendering and captions."""
import math
import re
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

FPS = 30
_STAMP = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})$")
_SENTENCE_END = re.compile(r"[。！？!?\.][”’\"'）)]*$")


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + "必须是有效数字。")
    return value


def _frame(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(label + "必须是非负整数帧。")
    return value


def _timestamp(text, index):
    match = _STAMP.fullmatch(text.strip())
    if not match:
        raise ValueError("第 %d 条字幕时间码格式不正确。" % index)
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def parse_srt(text: str, duration_ms: float) -> list:
    _number(duration_ms, "视频时长")
    if duration_ms <= 0:
        raise ValueError("视频时长必须大于零。")
    if not isinstance(text, str):
        raise ValueError("字幕必须是 UTF-8 文本。")
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("字幕文件没有有效条目。")
    cues = []
    for index, chunk in enumerate(re.split(r"\n[ \t]*\n", text), 1):
        lines = chunk.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit() or "-->" not in lines[1]:
            raise ValueError("第 %d 条字幕缺少编号、时间码或正文。" % index)
        times = lines[1].split("-->")
        if len(times) != 2:
            raise ValueError("第 %d 条字幕时间码格式不正确。" % index)
        start, end = (_timestamp(value, index) for value in times)
        body = "\n".join(lines[2:]).strip()
        if not body or start >= end:
            raise ValueError("第 %d 条字幕正文为空或结束时间不晚于开始时间。" % index)
        if end > duration_ms + 1e-6:
            raise ValueError("第 %d 条字幕超过视频时长，请检查时间码。" % index)
        if cues and start < cues[-1]["endMs"]:
            raise ValueError("第 %d 条字幕与前一条重叠或时间顺序错误，请校正字幕。" % index)
        cues.append({"id": "c%03d" % index, "startMs": start, "endMs": end, "text": body})
    return cues


def _quantize(value, rounding):
    return int((Decimal(str(value)) * FPS / 1000).to_integral_value(rounding=rounding))


def _risks(text):
    patterns = [("condition", r"如果|只有|只要|除非|前提|当.{0,12}时"),
                ("negation", r"不|没|无|别|勿|并非"),
                ("number", r"[0-9%％]|[零一二三四五六七八九十百千万]+(?:秒|分钟|小时|天|周|月|年|次|遍|条|句|项|步|页|人|元)|(?:至少|最多|仅|只有|只需|必须|不超过)[零一二三四五六七八九十百千万]+[个种套]"),
                ("context", r"因此|所以|但是|不过|这[个种些]|上述|前面|接着")]
    return [name for name, pattern in patterns if re.search(pattern, text)]


def build_blocks(cues, total_frames: int) -> list:
    _frame(total_frames, "总帧数")
    if total_frames == 0 or not cues:
        raise ValueError("视频和字幕都需要包含有效内容。")
    previous = 0
    ids = set()
    for index, cue in enumerate(cues, 1):
        start, end = _number(cue["startMs"], "字幕开始时间"), _number(cue["endMs"], "字幕结束时间")
        if start < previous or end <= start or end > total_frames * 1000 / FPS + 1e-6:
            raise ValueError("第 %d 条字幕重叠、越界或时间不合法。" % index)
        if cue["id"] in ids:
            raise ValueError("字幕编号重复。")
        ids.add(cue["id"])
        previous = end
    if len(cues) > 1 and not any(_SENTENCE_END.search(cue["text"].rstrip()) for cue in cues):
        raise ValueError("字幕缺少完整句末标点，请先按完整句校正字幕再导入。")
    groups, pending = [], []
    for cue in cues:
        pending.append(cue)
        if _SENTENCE_END.search(cue["text"].rstrip()):
            groups.append(pending)
            pending = []
    if pending:
        if groups:
            groups[-1].extend(pending)
        else:
            groups.append(pending)
    # No legal frame in a caption gap means the two semantic groups are atomic.
    merged = [groups[0]]
    for group in groups[1:]:
        left = _quantize(merged[-1][-1]["endMs"], ROUND_CEILING)
        right = _quantize(group[0]["startMs"], ROUND_FLOOR)
        if left > right:
            merged[-1].extend(group)
        else:
            merged.append(group)
    boundaries = [0]
    for before, after in zip(merged, merged[1:]):
        left = _quantize(before[-1]["endMs"], ROUND_CEILING)
        right = _quantize(after[0]["startMs"], ROUND_FLOOR)
        boundaries.append((left + right + 1) // 2)
    boundaries.append(total_frames)
    blocks = []
    for index, group in enumerate(merged):
        start, end = boundaries[index:index + 2]
        if end <= start:
            raise ValueError("字幕无法生成有效剪辑区间，请检查首尾时间码。")
        text = "\n".join(cue["text"] for cue in group)
        blocks.append({"id": "s%02d" % (index + 1), "order": index,
                       "cueIds": [cue["id"] for cue in group], "text": text,
                       "clipStartFrame": start, "clipEndFrame": end,
                       "riskHints": _risks(text)})
    return blocks


def build_spans(blocks, kept_ids) -> list:
    kept = set(kept_ids)
    known = {block["id"] for block in blocks}
    if not kept:
        raise ValueError("至少保留一段内容才能生成短片。")
    if kept - known:
        raise ValueError("保留列表包含不存在的片段。")
    if len(kept) != len(kept_ids) or len(known) != len(blocks):
        raise ValueError("片段编号重复。")
    spans, output_frame, previous_end = [], 0, 0
    for block in blocks:
        start = _frame(block["clipStartFrame"], "片段起点")
        end = _frame(block["clipEndFrame"], "片段终点")
        if start != previous_end or end <= start:
            raise ValueError("片段没有按原顺序完整覆盖源视频。")
        previous_end = end
        if block["id"] not in kept:
            continue
        if spans and spans[-1]["sourceEndFrame"] == start:
            spans[-1]["sourceEndFrame"] = end
            spans[-1]["blockIds"].append(block["id"])
        else:
            spans.append({"sourceStartFrame": start, "sourceEndFrame": end,
                          "outputStartFrame": output_frame, "blockIds": [block["id"]]})
        output_frame += end - start
    return spans


def map_cues(cues, spans, fps=FPS) -> list:
    if fps != FPS:
        raise ValueError("剪辑时间轴只支持 30 fps。")
    mapped = []
    output_frame, previous_end = 0, 0
    for span in spans:
        start = _frame(span["sourceStartFrame"], "剪辑起点")
        end = _frame(span["sourceEndFrame"], "剪辑终点")
        output = _frame(span["outputStartFrame"], "输出起点")
        if start < previous_end or end <= start or output != output_frame:
            raise ValueError("剪辑清单顺序或输出起点不正确。")
        previous_end = end
        output_frame += end - start
        a, b, offset = start * 1000 / fps, end * 1000 / fps, span["outputStartFrame"] * 1000 / fps
        for cue in cues:
            if cue["endMs"] <= a + 1e-7 or cue["startMs"] >= b - 1e-7:
                continue
            if cue["startMs"] < a - 1e-7 or cue["endMs"] > b + 1e-7:
                raise ValueError("字幕 %s 被切口拆开，请合并片段或校正字幕。" % cue["id"])
            mapped.append({"id": cue["id"], "startMs": max(0, offset + cue["startMs"] - a),
                           "endMs": offset + cue["endMs"] - a, "text": cue["text"]})
    return mapped


def duration_ms(spans) -> float:
    return sum(span["sourceEndFrame"] - span["sourceStartFrame"] for span in spans) * 1000 / FPS


def _format_stamp(value, separator):
    milliseconds = int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, milliseconds = divmod(remainder, 1000)
    return "%02d:%02d:%02d%s%03d" % (hours, minutes, seconds, separator, milliseconds)


def write_srt(cues) -> str:
    return "\n\n".join("%d\n%s --> %s\n%s" % (index, _format_stamp(cue["startMs"], ","),
                        _format_stamp(cue["endMs"], ","), cue["text"])
                        for index, cue in enumerate(cues, 1)) + "\n"


def write_vtt(cues) -> str:
    return "WEBVTT\n\n" + "\n\n".join("%d\n%s --> %s\n%s" % (index,
        _format_stamp(cue["startMs"], "."), _format_stamp(cue["endMs"], "."), cue["text"])
        for index, cue in enumerate(cues, 1)) + "\n"
