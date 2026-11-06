"""V2 immutable source coordinates, editable text, ordered clips and word cuts."""
import copy
import math
import re
from .timeline import build_spans, map_cues


def defaults(project):
    edit = copy.deepcopy(project['edit'])
    for key, value in {'order': [b['id'] for b in project['blocks']], 'deletedWordIds': [],
                       'captionEdits': {}, 'wordEdits': {}, 'notes': {}, 'recordings': {},
                       'pendingRewrites': {}, 'brief': ''}.items():
        edit.setdefault(key, value)
    return edit


def attach_words(project, raw_words):
    """Partition each block on measured word gaps; never interpolate character timing."""
    words = []
    for block in project['blocks']:
        start, end = block['clipStartFrame'], block['clipEndFrame']
        measured = [w for w in raw_words if start <= (w['startMs'] + w['endMs']) * .015 < end]
        measured.sort(key=lambda w: w['startMs'])
        # Quantize measured adjacent boundaries once. Sub-frame/overlapping units are merged.
        groups = []
        for word in measured:
            a = max(start, min(end - 1, round(word['startMs'] * .03)))
            b = max(a, min(end, round(word['endMs'] * .03)))
            if groups and (b <= a or word['startMs'] < groups[-1]['rawEndMs'] - 20):
                groups[-1]['end'] = max(groups[-1]['end'], b)
                groups[-1]['rawEndMs'] = max(groups[-1]['rawEndMs'], word['endMs'])
                groups[-1]['text'] += word['text']
            else:
                groups.append({'start': a, 'end': b, 'rawStartMs': word['startMs'], 'rawEndMs': word['endMs'],
                               'text': word['text'], 'confidence': word.get('confidence')})
        while groups:
            boundaries = [start] + [round((left['rawEndMs'] + right['rawStartMs']) * .015)
                                     for left, right in zip(groups, groups[1:])] + [end]
            bad = next((i for i in range(len(groups)) if boundaries[i+1] <= boundaries[i]), None)
            if bad is None: break
            if len(groups) == 1:
                groups = []; break
            target = max(0, bad-1) if bad == len(groups)-1 else bad
            left, right = groups[target:target+2]
            left.update(end=max(left['end'],right['end']), rawEndMs=max(left['rawEndMs'],right['rawEndMs']), text=left['text']+right['text'])
            groups.pop(target+1)
        for index, group in enumerate(groups):
            if boundaries[index+1] <= boundaries[index]:
                continue
            words.append({'id': '%s_w%03d' % (block['id'], index+1), 'blockId': block['id'],
                          'text': group['text'], 'startMs': group['start'] / .03, 'endMs': group['end'] / .03,
                          'clipStartFrame': boundaries[index], 'clipEndFrame': boundaries[index+1],
                          'confidence': group.get('confidence')})
    return words


def join_words(words, edits):
    result = ''.join(edits.get(w['id'], w['text']) for w in words).strip()
    return result


def timeline(project):
    if project.get('schemaVersion', 1) < 2:
        spans = build_spans(project['blocks'], project['edit']['keptBlockIds']) if project['edit']['keptBlockIds'] else []
        return spans, map_cues(project['cues'], spans) if spans else []
    edit = defaults(project)
    blocks = {b['id']: b for b in project['blocks']}
    if len(edit['order']) != len(blocks) or set(edit['order']) != set(blocks):
        raise ValueError('片段顺序不完整，请刷新后重试。')
    kept, deleted = set(edit['keptBlockIds']), set(edit['deletedWordIds'])
    output, spans, captions = 0, [], []
    for bid in edit['order']:
        if bid not in kept:
            continue
        block = blocks[bid]
        recording = edit['recordings'].get(bid)
        words = (recording or {}).get('words', [w for w in project.get('words', []) if w['blockId'] == bid])
        groups = []
        if words:
            for word in words:
                if word['id'] in deleted:
                    continue
                if groups and groups[-1]['end'] == word['clipStartFrame']:
                    groups[-1]['end'] = word['clipEndFrame']; groups[-1]['words'].append(word)
                else:
                    groups.append({'start': word['clipStartFrame'], 'end': word['clipEndFrame'], 'words': [word]})
        else:
            groups = [{'start': block['clipStartFrame'], 'end': block['clipEndFrame'], 'words': []}]
        for group in groups:
            a, b = group['start'], group['end']
            span = {'sourceStartFrame': a, 'sourceEndFrame': b, 'outputStartFrame': output, 'blockIds': [bid]}
            if recording:
                span.update(recordingId=recording['id'], audioStartFrame=a-block['clipStartFrame'])
            spans.append(span)
            if group['words']:
                text = join_words(group['words'], edit['wordEdits'])
                # Whole-block caption corrections retain their measured span; word editing requires clearing them.
                if bid in edit['captionEdits']:
                    text = edit['captionEdits'][bid]
                first, last = group['words'][0], group['words'][-1]
                ca = max(a, min(b-1, round(first['startMs'] * .03)))
                cb = min(b, max(ca+1, round(last['endMs'] * .03)))
                if text:
                    if text[-1] not in '。！？.!?': text=text.rstrip('，,；;')+'。'
                    captions.append({'id':'v%04d' % (len(captions)+1), 'startMs':(output+ca-a)/.03,
                                     'endMs':(output+cb-a)/.03, 'text':text})
            elif recording or bid in edit['captionEdits']:
                text = edit['captionEdits'].get(bid, (recording or {}).get('text', block['text']))
                if text:
                    captions.append({'id':'v%04d' % (len(captions)+1),'startMs':output/.03,'endMs':(output+b-a)/.03,'text':text})
            else:
                for cue in project['cues']:
                    if cue['id'] in block['cueIds']:
                        captions.append(dict(cue, startMs=(output-a)/.03+cue['startMs'], endMs=(output-a)/.03+cue['endMs']))
            output += b-a
    return spans, captions


def all_words(project):
    edit = defaults(project)
    replaced = edit['recordings']
    return [w for w in project.get('words', []) if w['blockId'] not in replaced] + [w for r in replaced.values() for w in r.get('words', [])]


def block_text(project, bid):
    edit=defaults(project)
    if bid in edit['captionEdits']:return edit['captionEdits'][bid]
    words=[w for w in all_words(project) if w['blockId']==bid and w['id'] not in edit['deletedWordIds']]
    if words:return join_words(words,edit['wordEdits'])
    if any(w['blockId']==bid for w in all_words(project)):return ''
    return next(b['text'] for b in project['blocks'] if b['id']==bid)


def apply_edit(project, action):
    """Mutate only an in-memory snapshot. Service performs one revisioned atomic save."""
    edit = defaults(project)
    project['edit'] = edit
    original=copy.deepcopy(edit)
    blocks = {b['id']: b for b in project['blocks']}
    bid = action.get('blockId')
    kind = action['type']
    if bid is not None and bid not in blocks:
        raise ValueError('找不到这个片段。')
    text = action.get('text', '').strip()
    if len(text) > 4000:
        raise ValueError('单段文字不能超过4000字。')
    if kind == 'set_brief':
        if len(text)>300:raise ValueError('剪辑主线最多300字。')
        edit['brief']=text
    elif kind == 'correct_caption':
        if not bid: raise ValueError('请选择要校对的片段。')
        if any(w['id'] in edit['deletedWordIds'] for w in all_words(project) if w['blockId'] == bid):
            raise ValueError('该段已有词级删减，请逐词校对，或恢复词语后整段校对。')
        if text: edit['captionEdits'][bid] = text
        else: edit['captionEdits'].pop(bid, None)
    elif kind == 'correct_word':
        wid = action.get('wordId')
        if not any(w['id'] == wid for w in all_words(project)): raise ValueError('词时间轴已变化，请刷新后重试。')
        if text: edit['wordEdits'][wid] = text
        else: edit['wordEdits'].pop(wid, None)
    elif kind == 'annotate':
        if not bid: raise ValueError('请选择要标注的片段。')
        if text: edit['notes'][bid] = text
        else: edit['notes'].pop(bid, None)
    elif kind in ['delete_words', 'restore_words']:
        ids = action.get('wordIds', [])
        words = {w['id']:w for w in all_words(project)}
        if not ids or len(ids)!=len(set(ids)) or any(i not in words for i in ids):
            raise ValueError('请选择有效的词语；没有时间轴时请先识别字幕。')
        if kind == 'delete_words':
            if any(words[i]['blockId'] in edit['lockedBlockIds'] for i in ids):
                raise ValueError('必留片段不能剪词，请先取消必留。')
            if any(words[i]['blockId'] in edit['captionEdits'] for i in ids):
                raise ValueError('整段校对文字绑定完整时间；请先恢复原字幕，再逐词校对或剪词。')
            edit['deletedWordIds'] = sorted(set(edit['deletedWordIds']) | set(ids))
        else:
            edit['deletedWordIds'] = [i for i in edit['deletedWordIds'] if i not in ids]
    elif kind == 'move_block':
        if not bid: raise ValueError('请选择要移动的片段。')
        order = edit['order']; index = order.index(bid)
        direction = action.get('direction')
        if direction not in [-1,1]: raise ValueError('移动方向无效。')
        target = index + direction
        if 0 <= target < len(order): order[index],order[target] = order[target],order[index]
    elif kind == 'set_rewrite':
        if not bid or bid in edit['lockedBlockIds']: raise ValueError('请先选择片段并取消必留，再修改说法。')
        if text: edit['pendingRewrites'][bid] = text
        else: edit['pendingRewrites'].pop(bid, None)
    elif kind == 'restore_audio':
        if not bid: raise ValueError('请选择片段。')
        recording = edit['recordings'].pop(bid, None)
        if recording:
            word_ids = {w['id'] for w in recording.get('words', [])}
            edit['deletedWordIds'] = [i for i in edit['deletedWordIds'] if i not in word_ids]
            edit['wordEdits'] = {i:t for i,t in edit['wordEdits'].items() if i not in word_ids}
        edit['captionEdits'].pop(bid, None)
    else:
        raise ValueError('不支持的精修操作。')
    if edit != original: edit['hasManualEdits'] = True
    return edit
