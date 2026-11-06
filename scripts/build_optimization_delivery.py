"""Bundle explicitly shareable review artifacts and source; never copy private data or caches."""
from pathlib import Path
import hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'deliverables/optimization'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[p for p in OUT.iterdir() if p.suffix in ['.md','.json','.png','.mp4','.srt'] and p.name not in ['EVIDENCE_INDEX.json','browser_failure.json','browser_failure.png']]
for p in (ROOT/'deliverables/v2').rglob('*'):
 if p.is_file() and p.suffix in ['.md','.json','.png','.pdf','.html','.mp4'] and 'failure' not in p.name:artifacts.append(p)
artifacts.extend([ROOT/'deliverables/history/README_V1.md',ROOT/'deliverables/review/INDEPENDENT_REVIEW_2026-11-06.md'])
entries=[]
for p in sorted(artifacts):
 rel=str(p.relative_to(ROOT));history='/v2/' in rel or '/history/' in rel
 entries.append({'path':rel,'format':p.suffix[1:],'sha256':digest(p),'bytes':p.stat().st_size,
  'version':'V2 baseline 70e3b6e' if history else '2026-11-06 review optimization; source commit in Git history',
  'access':'local /delivery or delivery.zip via SSH port 8767; private data excluded',
  'github':p.suffix in ['.md','.json','.srt','.png']})
sources=[]
for folder in ['backend','frontend/src','frontend/tests','scripts','tests']:
 for p in (ROOT/folder).rglob('*'):
  if p.is_file() and p.suffix in ['.py','.js','.cjs','.mjs','.css','.sh'] and '__pycache__' not in str(p):sources.append(p)
for p in ROOT.iterdir():
 if p.is_file() and (p.suffix=='.md' or p.name.startswith('requirements')):sources.append(p)
for name in ['frontend/index.html','frontend/build.mjs','frontend/package.json','fixtures/real_tao_v2/manifest.json','fixtures/real_ying_v2/manifest.json']:
 sources.append(ROOT/name)
fixtures=[p for p in (ROOT/'fixtures').rglob('*') if p.is_file() and '_work' not in p.parts and p.suffix in ['.json','.srt','.mp4','.jpg','.md']]
source_hash=hashlib.sha256(''.join(str(p.relative_to(ROOT))+':'+digest(p)+'\n' for p in sorted(sources)).encode()).hexdigest()
index={'reviewCommit':'0166eb6f748e53677d97f2df863128611e189980','implementationBase':'70e3b6e5e35bc057cbe7049b6ed570afd7bf170b',
       'sourceContentSha256':source_hash,'note':'Index excludes itself and ZIP to avoid circular hashes. Live /api/deliverables also hashes ZIP. GitHub status describes intended publication of this batch.', 'artifacts':entries}
(OUT/'EVIDENCE_INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(OUT/'delivery.zip','w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
 for p in sorted(set(sources+fixtures+artifacts+[OUT/'EVIDENCE_INDEX.json'])):z.write(p,str(p.relative_to(ROOT)))
print(json.dumps({'files':len(sources)+len(artifacts)+1,'zipBytes':(OUT/'delivery.zip').stat().st_size,'sha256':digest(OUT/'delivery.zip')},indent=2))
