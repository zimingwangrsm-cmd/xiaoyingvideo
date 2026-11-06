"""Isolated CPU worker. Model output is measured, never substituted by fixture text."""
import argparse
import json
import os
import math
from pathlib import Path
import time


def transcribe(source, model_path):
    from faster_whisper import WhisperModel
    from opencc import OpenCC
    convert = OpenCC('t2s').convert
    model = WhisperModel(str(model_path), device='cpu', compute_type='int8', cpu_threads=8, num_workers=1,
                         local_files_only=True)
    segments, info = model.transcribe(str(source), language='zh', beam_size=5, word_timestamps=True,
                                     vad_filter=True, condition_on_previous_text=False, temperature=0,
                                     vad_parameters={'min_silence_duration_ms': 400})
    cues, words = [], []
    for segment in segments:
        if segment.no_speech_prob > .8 or segment.avg_logprob < -1.2:
            continue
        text = convert(segment.text.strip())
        if not text or segment.end <= segment.start:
            continue
        if text[-1] not in '。！？.!?': text += '。'
        start_ms=math.ceil(round(segment.start*30)/.03)
        end_ms=math.floor(round(segment.end*30)/.03)
        if cues: start_ms=max(start_ms,cues[-1]['endMs'])
        if end_ms<=start_ms:
            if cues:cues[-1]['text']+=text
        else:
            cues.append({'id':'c%03d' % (len(cues)+1), 'startMs':start_ms, 'endMs':end_ms, 'text':text})
        for word in segment.words or []:
            if word.end >= word.start and word.word.strip():
                words.append({'text':convert(word.word), 'startMs':word.start*1000,
                              'endMs':word.end*1000, 'confidence':word.probability})
    if not cues or not words:
        raise ValueError('没有识别到可用的中文口播，请检查音轨或提供校对后的SRT。')
    return {'cues':cues,'words':words,'language':info.language,
            'engine':'faster-whisper','model':'medium','device':'cpu','computeType':'int8',
            'transcriptVerified':False}


def separate(source, output):
    import torch
    torch.set_num_threads(8)
    from demucs.separate import main
    main(['-n','htdemucs','--two-stems','vocals','-d','cpu','-j','1','--segment','7',
          '--shifts','0','-o',str(output),str(source)])
    folder=output/'htdemucs'/source.stem
    return {'vocals':str(folder/'vocals.wav'),'background':str(folder/'no_vocals.wav'),'engine':'htdemucs'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('kind',choices=['transcribe','separate'])
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',type=Path)
    args=parser.parse_args()
    start=time.monotonic()
    try:
        result=transcribe(args.source,args.model) if args.kind=='transcribe' else separate(args.source,args.output.parent/'stems')
        result['elapsedSeconds']=round(time.monotonic()-start,3)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    except Exception as exc:
        # Detailed dependency/decoder errors remain in private worker logs.
        print(type(exc).__name__+': '+str(exc),flush=True)
        raise SystemExit(1)

if __name__=='__main__':main()
