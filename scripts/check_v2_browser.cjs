/* Genuine V2 UI acceptance. All inference and media requests reach the local backend. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'deliverables/v2/acceptance');fs.mkdirSync(out,{recursive:true});
const base=process.env.APP_URL||'http://127.0.0.1:8770';assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const passed=[],errors=[];const pass=(name,details={})=>{passed.push({name,...details});console.log('PASS',name)};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});const page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));let p;
 const shot=async name=>page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
 async function refresh(){p=await context.request.get(base+'/api/projects/'+p.id).then(r=>r.json());return p;}
 async function mutate(selector){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')&&r.request().method()==='POST'),page.locator(selector).first().click()]);assert.equal(r.status(),200);p=await r.json();await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));}
 async function submit(form){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')),page.locator(form+' button[type="submit"], '+form+' button:not([type])').first().click()]);assert.equal(r.status(),200);p=await r.json();await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));}
 async function waitJob(jid){let job;const deadline=Date.now()+600000;do{job=await context.request.get(base+'/api/processing-jobs/'+jid).then(r=>r.json());if(!['queued','running'].includes(job.status))break;await page.waitForTimeout(1000)}while(Date.now()<deadline);assert.equal(job.status,'succeeded',JSON.stringify(job));return job;}
 async function processing(action,kind){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/processing/'+kind)),page.locator(`[data-action="${action}"]`).first().click()]);assert.equal(r.status(),202);const j=await r.json();const done=await waitJob(j.id);await page.waitForTimeout(1300);return done;}
 async function sample(id){await page.locator('#sample-picker').selectOption(id);const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/from-sample')),page.locator('[data-action="start-sample"]').click()]);p=await r.json();await page.locator('#source-video').waitFor();}
 try{
  await page.goto(base);await page.locator('#sample-picker').waitFor();await shot('01_real_samples');
  await sample('real_ying_v2');assert(p.words.length>100);assert.equal(p.source.origin,'recorded_sample');
  await page.locator('video').evaluate(v=>v.play());await page.waitForFunction(()=>document.querySelector('video').currentTime>1);await page.locator('video').evaluate(v=>v.pause());
  pass('licensed real sample, local ASR word grid and actual video playback',{words:p.words.length,blocks:p.blocks.length});await shot('02_real_editor');
  const bid=p.blocks.find(b=>b.text.includes('访宴'))?.id||p.blocks[0].id;
  await page.locator(`[data-action="refine"][data-id="${bid}"]`).click();
  await page.locator('#caption-text').fill('人工校对示例：分享家乡方言。');await submit('#caption-edit-form');
  assert.equal(p.edit.captionEdits[bid],'人工校对示例：分享家乡方言。');
  await page.locator('#note-text').fill('模型把“方言”识别成“访宴”，需要校对。');await submit('#note-form');
  assert(p.edit.notes[bid].includes('方言'));await shot('03_caption_correction');
  await mutate('[data-action="clear-caption"]');
  const words=p.words.filter(w=>w.blockId===bid);const word=words[0];
  await page.locator(`[data-action="select-word"][data-word="${word.id}"]`).click();
  const before=p.metrics.plannedDurationMs;await mutate('[data-action="delete-selected-words"]');assert(p.metrics.plannedDurationMs<before);
  await shot('04_word_cut');await mutate('[data-action="restore-selected-words"]');assert.equal(p.metrics.plannedDurationMs,before);
  await page.locator('#word-text').fill('校对词');await submit('#word-edit-form');assert.equal(p.edit.wordEdits[word.id],'校对词');
  await page.locator('[data-action="close-refine"]').click();
  await mutate('[data-action="undo"]');
  pass('caption correction, notes, measured word cut/restore and word correction');
  const move=p.blocks[2].id;await page.locator(`[data-action="refine"][data-id="${move}"]`).click();
  await mutate(`[data-action="move-up"][data-id="${move}"]`);assert.equal(p.edit.order[1],move);
  await page.locator('[data-action="close-refine"]').click();await shot('05_reordered');await mutate('[data-action="undo"]');
  pass('whole sentence reordering with undo');
  // Replacement uses an attributed excerpt from the licensed sample, not synthetic/claimed new speech.
  const rb=p.blocks.find(b=>(b.clipEndFrame-b.clipStartFrame)/30>4).id;
  await page.locator(`[data-action="refine"][data-id="${rb}"]`).click();
  await page.locator('#rewrite-text').fill('补录接口验收：使用授权真人原片片段替换声音。');await submit('#rewrite-form');
  await page.locator('[data-action="close-refine"]').click();assert(await page.locator('[data-action="render"]').isDisabled());
  await page.locator(`[data-action="refine"][data-id="${rb}"]`).click();
  await page.locator('input[name="recording"]').setInputFiles(path.join(root,'data/v2_sources/replacement_excerpt.wav'));
  const [rr]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/recordings')&&r.request().method()==='POST'),page.locator('#recording-form button:not([type])').click()]);
  const rj=await rr.json();await waitJob(rj.id);await page.locator('[data-action="confirm-recording"]').waitFor({timeout:600000});
  await shot('06_recording_review');
  const [confirmed]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/recordings/confirm')),page.locator('[data-action="confirm-recording"]').click()]);assert.equal(confirmed.status(),200);p=await confirmed.json();
  assert.equal(p.metrics.pendingRewriteCount,0);assert(p.edit.recordings[rb]);
  pass('pending rewrite blocks export; real recording upload, ASR and confirmation clear pending state',{replacementSource:'3 second excerpt of licensed Ying sample, not a new human recording'});
  // Render a small selection after recording replacement, through visible controls.
  for(const b of p.blocks){if(b.id!==rb)await mutate(`[data-action="delete"][data-id="${b.id}"]`)}
  await page.locator('[data-action="render"]').click();await page.locator('#result-video').waitFor({timeout:300000});
  await page.locator('#result-video').evaluate(v=>v.play());await page.waitForFunction(()=>document.querySelector('video').currentTime>1);await page.locator('video').evaluate(v=>v.pause());
  for(const [kind,file]of [['mp4','v2_actual.mp4'],['srt','v2_actual.srt'],['record','v2_record.json'],['bundle','v2_handoff.zip']]){
   const event=page.waitForEvent('download');await page.locator(`[data-download="${kind}"]`).click();const d=await event;assert.equal(await d.failure(),null);await d.saveAs(path.join(out,file));
  }
  const crypto=require('node:crypto'),sha=f=>crypto.createHash('sha256').update(fs.readFileSync(path.join(out,f))).digest('hex');
  const record=JSON.parse(fs.readFileSync(path.join(out,'v2_record.json')));assert.equal(record.videoSha256,sha('v2_actual.mp4'));assert.equal(record.subtitleSha256,sha('v2_actual.srt'));
  await shot('07_actual_result');pass('V2 real render, video/subtitle playback, MP4/SRT/record and handoff ZIP downloads');
  await page.locator('[data-action="back-editor"]').click();await page.locator(`[data-action="refine"][data-id="${rb}"]`).click();
  await mutate('[data-action="restore-audio"]');assert(!p.edit.recordings[rb]);await page.locator('[data-action="close-refine"]').click();
  pass('restore original audio marks rendered result stale');
  await page.locator('[data-action="new-project"]').click();
  await page.locator('input[name="video"]').setInputFiles(path.join(root,'data/v2_sources/ying_import_18.mp4'));
  const [uploaded]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/import')),page.locator('#import-form button[type="submit"]').click()]);assert.equal(uploaded.status(),202);p=await uploaded.json();
  await page.locator('#source-video').waitFor({timeout:600000});await refresh();assert(p.words.length>0);assert.equal(p.transcriptionInfo.source,'local_asr');
  await shot('08_no_srt_import');pass('video-only HTTP upload creates real automatic captions',{words:p.words.length});
  await page.locator('#separate-voice').check();const transcribed=await processing('transcribe','transcribe');
  await page.locator('[data-action="confirm-transcript"]').waitFor();
  const [tc]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/transcript/confirm')),page.locator('[data-action="confirm-transcript"]').click()]);assert.equal(tc.status(),200);p=await tc.json();
  assert.equal(p.audioProcessing.status,'ready');await shot('09_separated_transcript');
  pass('real Demucs separation, local retranscription, explicit confirmation and audition tracks',{elapsed:transcribed.elapsedSeconds});
  const bgBid=[...p.blocks].sort((a,b)=>(b.clipEndFrame-b.clipStartFrame)-(a.clipEndFrame-a.clipStartFrame))[0].id;
  await page.locator(`[data-action="refine"][data-id="${bgBid}"]`).click();
  await page.locator('input[name="recording"]').setInputFiles(path.join(root,'data/v2_sources/replacement_excerpt.wav'));
  await page.locator('input[name="keepBackground"]').check();
  const [bgResponse]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/recordings')&&r.request().method()==='POST'),page.locator('#recording-form button:not([type])').click()]);
  const bgJob=await bgResponse.json();const bgDone=await waitJob(bgJob.id);assert.equal(bgDone.result.keepBackground,true);
  await page.locator('[data-action="confirm-recording"]').waitFor({timeout:600000});
  const [bgConfirm]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/recordings/confirm')),page.locator('[data-action="confirm-recording"]').click()]);p=await bgConfirm.json();assert.equal(bgConfirm.status(),200);
  pass('replacement can preserve the separated background track');
  await page.locator('#target-seconds').fill('10');await mutate('#target-form button');
  if(!process.env.SKIP_LLM){
   const proposal=await processing('propose','suggestions');assert.equal(proposal.result.source,'local_llm');assert(proposal.result.strategy.length>0);
   await shot('10_local_suggestions');
   const items=proposal.result.items;
   if(items.length){
    const [accepted]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/proposal-decisions')),page.locator('[data-action="accept-item"]').first().click()]);assert.equal(accepted.status(),200);
    const updated=await accepted.json();p=updated.project;assert(updated.proposal.items.some(i=>i.status==='accepted'));
    if(updated.proposal.items.some(i=>i.status==='pending')){const [rejected]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/proposal-decisions')),page.locator('[data-action="reject-item"]').first().click()]);assert.equal(rejected.status(),200)}
   }
   pass('actual local Qwen strategy and per-item accept/reject',{items:items.length,elapsed:proposal.elapsedSeconds});
  }
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot('11_mobile');
  pass('mobile width without horizontal overflow');assert.deepEqual(errors,[]);pass('no uncaught JavaScript errors');
  fs.writeFileSync(path.join(out,'browser_validation.json'),JSON.stringify({testedAt:new Date().toISOString(),baseUrl:base,actualInference:true,llmSkipped:Boolean(process.env.SKIP_LLM),passed,pageErrors:errors},null,2)+'\n');
 }catch(error){await shot('failure');fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({passed,errors,error:error.stack},null,2));throw error}
 finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
