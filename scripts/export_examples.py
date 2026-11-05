"""Exercise the real service without HTTP; this is not a browser recording."""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import Settings
from backend.app.service import Service
from backend.app.schemas import ActionRequest, ProposalRequest, RenderRequest

service = Service(Settings(data_dir=ROOT/'data'/'delivery_examples', model_mode='rules'))
owner, _ = service.session(None)
results = []
try:
    for label, target, keep in [
        ('short_90', 90000, ['s01','s03','s04','s05','s07','s10','s12']),
        ('short_60', 60000, ['s03','s04','s05','s10','s12']),
        ('restored_all', 180000, None),
    ]:
        p = service.from_sample(owner, 'interview_intro_v1')
        if p['state'] != 'ready': raise RuntimeError(p['error'])
        def act(action):
            global p
            p=service.action(owner,p['id'],ActionRequest(expectedRevision=p['revision'],action=action))
        act({'type':'set_target','targetMs':target})
        act({'type':'lock','blockIds':['s03','s04','s05']})
        proposal=service.proposal(owner,p['id'],ProposalRequest(expectedRevision=p['revision'],mode='rules'))
        act({'type':'apply_proposal','proposalId':proposal['id']})
        act({'type':'restore_all'})
        if keep:
            act({'type':'delete','blockIds':[b['id'] for b in p['blocks'] if b['id'] not in keep]})
        job=service.render(owner,p['id'],RenderRequest(expectedRevision=p['revision'],allowOverTarget=False))
        service.futures[job['id']].result(timeout=300)
        job=service.get_job(owner,job['id'])
        if job['status']!='succeeded': raise RuntimeError(job)
        folder=ROOT/'deliverables'/'examples'/label
        folder.mkdir(parents=True,exist_ok=True)
        for kind,name in [('video','koubo.mp4'),('srt','koubo.srt'),('vtt','koubo.vtt'),('record','koubo_record.json')]:
            shutil.copyfile(service.artifact_path(owner,job['artifactId'],kind),folder/name)
        results.append({'label':label,'actualDurationMs':job['actualDurationMs'],'plannedDurationMs':job['plannedDurationMs'],
                        'targetMet':job['targetMet'],'blocks':p['edit']['keptBlockIds'],
                        'output':str(folder.relative_to(ROOT)), 'method':'Direct Service call; not HTTP/browser validation'})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    (ROOT/'deliverables'/'example_outputs.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
finally:
    service.close()
