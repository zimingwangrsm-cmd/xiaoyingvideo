"""Real inference comparison on a licensed voice excerpt and a controlled music mix."""
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.config import Settings
from backend.app.speech import run_worker

if __name__=='__main__':
 settings=Settings(data_dir=ROOT/'data/v2_speech_eval')
 folder=ROOT/'data/v2_speech_eval';folder.mkdir(parents=True,exist_ok=True)
 clean=ROOT/'data/v2_sources/tao_24s.wav';mixed=ROOT/'data/v2_sources/tao_music_24.mp4'
 results={}
 for name,source in [('clean',clean),('mixed',mixed)]:
  r=run_worker(settings,'transcribe',source,folder/(name+'.json'))
  results[name]={'text':''.join(c['text'] for c in r['cues']),'elapsedSeconds':r['elapsedSeconds'],'cueCount':len(r['cues'])}
 stems=run_worker(settings,'separate',mixed,folder/'stems.json')
 r=run_worker(settings,'transcribe',Path(stems['vocals']),folder/'separated.json')
 results['separated']={'text':''.join(c['text'] for c in r['cues']),'elapsedSeconds':r['elapsedSeconds'],'cueCount':len(r['cues'])}
 results['separationSeconds']=stems['elapsedSeconds']
 results['method']='Real faster-whisper medium CPU int8 and Demucs htdemucs; 24-second licensed Tao speech with locally generated instrumental chord. Clean ASR is a comparison, not human ground truth.'
 results['groundTruthVerified']=False
 results['bgm']='Three synthesized sine tones at 220/277.18/329.63Hz with amplitude modulation; no downloaded music.'
 output=ROOT/'deliverables/v2/bgm_validation.json';output.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps(results,ensure_ascii=False,indent=2))
