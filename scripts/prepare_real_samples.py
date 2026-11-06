"""Create source-attributed real samples after local ASR. Never modifies V1 fixtures."""
from pathlib import Path
import json
import sys
import subprocess
import argparse
import urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.config import Settings
from backend.app.media import probe_media,sha256_file
from backend.app.speech import run_worker
from backend.app.timeline import write_srt

SOURCES=[
 ('real_tao_v2','真人口播：Tao的语言与生活','Wikitongues, Teddy Nee',
 'https://commons.wikimedia.org/wiki/File:WIKITONGUES-_Tao_speaking_Yunnan_Mandarin_with_Thai_and_Taiwanese_accent.webm',128.2),
 ('real_ying_v2','真人口播：Ying介绍家乡语言','Wikitongues, Ying Li',
 'https://commons.wikimedia.org/wiki/File:WIKITONGUES-_Ying_speaking_Henan_Chinese.webm',150),
]
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--retranscribe',action='store_true');args=parser.parse_args()
 settings=Settings(data_dir=ROOT/'data/v2_samples')
 for sid,title,author,url,length in SOURCES:
  folder=ROOT/'fixtures'/sid;folder.mkdir(parents=True,exist_ok=True);source=folder/'canonical.mp4'
  if not source.is_file():
   media_url={
    'real_tao_v2':'https://upload.wikimedia.org/wikipedia/commons/9/9d/WIKITONGUES-_Tao_speaking_Yunnan_Mandarin_with_Thai_and_Taiwanese_accent.webm',
    'real_ying_v2':'https://upload.wikimedia.org/wikipedia/commons/7/7f/WIKITONGUES-_Ying_speaking_Henan_Chinese.webm',
   }[sid]
   raw=ROOT/'data/v2_sources'/(sid+'.webm');raw.parent.mkdir(parents=True,exist_ok=True)
   if not raw.is_file():
    temporary=raw.with_suffix('.part');urllib.request.urlretrieve(media_url,temporary);temporary.replace(raw)
   scale='1080:606' if sid=='real_tao_v2' else '1280:720'
   subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(raw),'-vf',
    'fps=fps=30:start_time=0,scale='+scale+',setsar=1,tpad=stop_mode=clone:stop_duration=2',
    '-c:v','libx264','-threads','2','-preset','veryfast','-crf','21','-pix_fmt','yuv420p',
    '-c:a','aac','-ar','48000','-af','aresample=48000:async=1:first_pts=0,apad','-t',str(length),
    '-movflags','+faststart',str(source)],check=True)

  result_path=folder/'transcription.json'
  if args.retranscribe or not result_path.exists():run_worker(settings,'transcribe',source,result_path)
  result=json.loads(result_path.read_text());info=probe_media(source)
  for c in result['cues']:c['endMs']=min(c['endMs'],info['totalFrames']/.03)
  (folder/'sample.srt').write_text(write_srt(result['cues']),encoding='utf-8')
  subprocess.run(['ffmpeg','-v','error','-y','-ss','10','-i',str(source),'-frames:v','1',str(folder/'poster.jpg')],check=True)
  manifest={'schemaVersion':2,'id':sid,'title':title,'description':'公开授权真人语言分享，有口音；本机识别字幕含待校对词语，可精修、剪词和重排。',
    'origin':'recorded_sample','label':'真人口播 · 本机识别字幕','videoFile':'canonical.mp4','subtitleFile':'sample.srt',
    'sourceSha256':sha256_file(source),'transcriptSha256':sha256_file(folder/'sample.srt'),
    'durationMs':info['totalFrames']/.03,'totalFrames':info['totalFrames'],'author':author,'sourceUrl':url,
    'license':'CC BY-SA 4.0','licenseUrl':'https://creativecommons.org/licenses/by-sa/4.0/',
    'licenseNote':'保留署名、来源与许可；截取/转换后的媒体及其剪辑衍生内容沿用CC BY-SA 4.0。无原作者背书。',
    'changes':'转为H.264/AAC、30fps/48kHz；采用开头%.1f秒；必要时延长末帧覆盖语音；自动生成简体中文字幕。'%length,
    'transcriptVerified':False,'transcriptReview':'Automatic recognition; requires creator review.','recommendedLockedIds':[],
    'asr':{k:v for k,v in result.items() if k not in ['cues','words']}}
  # Preserve the visible, editorial preset when refreshing generated ASR metadata.
  previous=json.loads((folder/'manifest.json').read_text()) if (folder/'manifest.json').exists() else {}
  if previous.get('samplePreset'):
   for key in ['title','description','samplePreset','showcaseUrl','showcaseLabel']:
    if key in previous:manifest[key]=previous[key]
  (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
  print(sid,len(result['cues']),len(result['words']),flush=True)
