/* Actual browser MediaRecorder with a declared fixture microphone; actual HTTP/ASR/render.
   Proposal data is deterministic only for layout/decision coverage, not a model-quality claim. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),base=process.env.APP_URL||'http://127.0.0.1:8776';
const out=path.join(root,'deliverables/recording_layout');fs.mkdirSync(out,{recursive:true});
const checks=[],errors=[];const pass=name=>{checks.push(name);console.log('PASS',name)};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,args:['--disable-audio-output','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+path.join(root,'data/v2_sources/replacement_excerpt.wav')]});
 const c=await browser.newContext({viewport:{width:1440,height:1000},permissions:['microphone'],acceptDownloads:true});const page=await c.newPage();page.on('pageerror',e=>errors.push(e.message));let p;
 // Observe stream teardown without replacing getUserMedia or MediaRecorder.
 await page.addInitScript(()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async args=>{const stream=await original(args);window.lastCaptureStream=stream;return stream}});
 const click=selector=>page.locator(selector).first().click();
 async function sample(){await page.locator('#sample-picker').selectOption('real_tao_v2');const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/from-sample')),click('[data-action="start-sample"]')]);p=await r.json();await page.locator('#source-video').waitFor();}
 async function action(selector){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')),click(selector)]);assert.equal(r.status(),200);p=await r.json();await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));}
 try{
  await page.goto(base);await sample();await click('[data-action="record-line"][data-id="s01"]');
  assert(await page.locator('[data-action="start-recording"]').isDisabled());await action('.refine-panel [data-action="unlock"]');
  await click('[data-action="start-recording"]');await page.locator('#recording-timer').waitFor();await page.waitForTimeout(2500);
  await page.keyboard.press('Escape');assert(await page.locator('#refine-dialog').isVisible());
  await click('[data-action="stop-recording"]');await page.locator('#take-audio').waitFor({timeout:15000});
  assert(await page.evaluate(()=>window.lastCaptureStream.getTracks().every(t=>t.readyState==='ended')));
  const duration=await page.locator('#take-audio').evaluate(a=>new Promise(resolve=>{if(a.readyState)resolve(a.duration);else a.addEventListener('loadedmetadata',()=>resolve(a.duration),{once:true})}));assert(duration>1&&duration<6.6);
  await page.locator('#take-audio').evaluate(a=>a.play());await page.waitForTimeout(400);assert(await page.locator('#take-audio').evaluate(a=>a.currentTime)>.1);await page.locator('#take-audio').evaluate(a=>a.pause());
  await page.screenshot({path:path.join(out,'sentence-recording.png'),fullPage:true});pass('real MediaRecorder capture, bounded WAV, preview, locked protection and microphone release');
  await click('[data-action="close-refine"]');await click('[data-action="record-line"][data-id="s02"]');assert.equal(await page.locator('#take-audio').count(),0);
  await click('[data-action="close-refine"]');await click('[data-action="record-line"][data-id="s01"]');assert(await page.locator('#take-audio').isVisible());pass('takes stay bound to project and sentence and survive drawer reopen');
  const [upload]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/recordings')&&r.request().method()==='POST'),click('#recording-form button:not([type])')]);assert.equal(upload.status(),202);
  const job=await upload.json();assert.equal(job.intent.blockId,'s01');assert(job.intent.fileName.endsWith('.wav'));
  await page.locator('[data-action="confirm-recording"]').waitFor({timeout:180000});await click('[data-action="confirm-recording"]');await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  p=await c.request.get(base+'/api/projects/'+p.id).then(r=>r.json());assert(p.edit.recordings.s01);pass('browser-recorded WAV reaches actual ASR and explicit sentence replacement');
  // Uploaded files use the same preview and confirmation pipeline.
  await click('[data-action="record-line"][data-id="s01"]');await click('[data-action="recording-mode"][data-mode="upload"]');await page.locator('input[name="recording"]').setInputFiles(path.join(root,'data/v2_sources/replacement_excerpt.wav'));
  assert(await page.locator('#take-audio').isVisible());await click('[data-action="discard-take"]');assert.equal(await page.locator('#take-audio').count(),0);await click('[data-action="close-refine"]');pass('upload option, local preview and discard remain available');
  // Every sentence permits up to one minute; the cap must release capture automatically.
  const short=p.blocks.filter(b=>!p.edit.lockedBlockIds.includes(b.id)).sort((a,b)=>(a.clipEndFrame-a.clipStartFrame)-(b.clipEndFrame-b.clipStartFrame))[0];
  await click(`[data-action="record-line"][data-id="${short.id}"]`);await click('[data-action="start-recording"]');await page.locator('#take-audio').waitFor({timeout:75000});assert(await page.evaluate(()=>window.lastCaptureStream.getTracks().every(t=>t.readyState==='ended')));
  await click('[data-action="discard-take"]');await click('[data-action="start-recording"]');await page.locator('#recording-timer').waitFor();await click('[data-action="cancel-recording"]');assert.equal(await page.locator('#take-audio').count(),0);assert(await page.evaluate(()=>window.lastCaptureStream.getTracks().every(t=>t.readyState==='ended')));await click('[data-action="close-refine"]');pass('automatic one-minute stop and explicit cancel release microphone');
  const beforeHeight=await page.evaluate(()=>document.documentElement.scrollHeight);
  const proposalId=crypto.randomBytes(16).toString('hex'),jid=crypto.randomBytes(16).toString('hex');
  const items=p.blocks.filter(b=>!p.edit.lockedBlockIds.includes(b.id)&&b.id!=='s01').slice(0,24).map((b,i)=>({id:'i'+String(i+1).padStart(2,'0'),blockId:b.id,type:'delete_block',before:b.text,after:'测试删除此段',reason:'确定性布局验收：检查多项建议时的滚动和确认。',status:'pending',action:{type:'delete',blockIds:[b.id]},durationDeltaMs:-(b.clipEndFrame-b.clipStartFrame)/.03}));
  const fixture={id:proposalId,projectId:p.id,baseRevision:p.revision,source:'rules',strategy:'此为24项确定性布局验收候选，不代表本地模型推理质量。',items,currentDurationMs:p.metrics.plannedDurationMs,estimatedDurationMs:30000};
  const folder=path.join(root,'data/recording_layout_acceptance/projects',p.id,'proposals_v2');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,proposalId+'.json'),JSON.stringify(fixture));
  await page.route('**/processing/suggestions',r=>r.fulfill({status:202,json:{id:jid,projectId:p.id,status:'queued',kind:'suggestions'}}));
  await page.route('**/processing-jobs/'+jid,r=>r.fulfill({status:200,json:{id:jid,projectId:p.id,kind:'suggestions',status:'succeeded',phase:'done',baseRevision:p.revision,result:fixture}}));
  await click('[data-action="propose"]');await page.locator('#suggestion-list').waitFor();
  assert.equal(await page.locator('.suggestion-item').count(),24);
  const dimensions=await page.evaluate(()=>{const list=document.querySelector('#suggestion-list'),a=document.querySelector('.preview-panel').getBoundingClientRect(),b=document.querySelector('#proposal-v2').getBoundingClientRect();return{height:document.documentElement.scrollHeight,listHeight:list.clientHeight,listScroll:list.scrollHeight,left:a.left,right:b.left,overlap:Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)}});
  assert(dimensions.listScroll>dimensions.listHeight*2);assert(dimensions.height<beforeHeight+700);assert(dimensions.left<dimensions.right&&dimensions.overlap>100);assert(dimensions.listHeight<=650);
  await page.screenshot({path:path.join(out,'balanced-suggestions.png'),fullPage:true});pass('24 suggestions occupy the right pane with bounded scrolling, alongside preview');
  for(const selector of ['[data-action="accept-item"][data-item="i01"]','[data-action="reject-item"][data-item="i02"]']){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/proposal-decisions')),click(selector)]);assert.equal(r.status(),200)}
  await click('[data-action="proposal-filter"][data-filter="rejected"]');assert.equal(await page.locator('.suggestion-item').count(),1);
  await click('[data-action="proposal-filter"][data-filter="pending"]');assert.equal(await page.locator('.suggestion-item').count(),22);
  await click('[data-action="workspace-tab"][data-tab="transcript"]');assert(await page.locator('#block-list').isVisible());await click('[data-action="workspace-tab"][data-tab="suggestions"]');assert(await page.locator('#suggestion-list').isVisible());pass('accept/reject filters and transcript/suggestions tabs stay functional');
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('#review-column').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'mobile-suggestions.png'),fullPage:true});
  await click('[data-action="workspace-tab"][data-tab="transcript"]');await click('[data-action="record-line"][data-id="s01"]');await click('[data-action="start-recording"]');await page.locator('#recording-timer').waitFor();await page.waitForTimeout(500);await click('[data-action="stop-recording"]');await page.locator('#take-audio').waitFor();await click('[data-action="discard-take"]');await click('[data-action="close-refine"]');pass('mobile-width suggestions and complete record/stop/preview/discard controls');
  await page.unrouteAll();await page.setViewportSize({width:1440,height:1000});
  // Short engineering render verifies the new audio; this is not the AI showcase.
  p=await c.request.get(base+'/api/projects/'+p.id).then(r=>r.json());
  const cut=p.edit.keptBlockIds.filter(id=>!['s01','s03','s08','s37'].includes(id));
  const trimmed=await c.request.post(base+'/api/projects/'+p.id+'/actions',{data:{expectedRevision:p.revision,action:{type:'delete',blockIds:cut}}});assert.equal(trimmed.status(),200);
  await page.reload();await page.locator('#source-video').waitFor();await click('[data-action="render"]');await page.locator('#result-video').waitFor({timeout:180000});
  const download=page.waitForEvent('download');await click('[data-download="mp4"]');await(await download).saveAs(path.join(root,'data/recording_layout_export.mp4'));pass('confirmed microphone replacement renders and downloads as actual MP4');
  const denied=await browser.newContext();await denied.grantPermissions([],{origin:base});const d=await denied.newPage();await d.goto(base);await d.locator('#sample-picker').selectOption('interview_intro_v1');await d.locator('[data-action="start-sample"]').click();await d.locator('[data-action="record-line"][data-id="s01"]').click();await d.locator('[data-action="start-recording"]').click();await d.locator('#recording-form [role="alert"]').waitFor();assert((await d.locator('#recording-form [role="alert"]').textContent()).includes('权限'));await denied.close();pass('denied microphone permission gives an actionable upload fallback');
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'browser_validation.json'),JSON.stringify({checks,layout:dimensions,pageErrors:errors,microphone:'Chromium fixture device using attributed source audio; actual getUserMedia/MediaRecorder/WAV/HTTP/ASR/render, not a physical-microphone or human-listening claim',suggestions:'24-item deterministic fixture + real decision API; model behavior unchanged'},null,2)+'\n');
 }catch(e){await page.screenshot({path:path.join(root,'data/recording_layout_failure.png'),fullPage:true});throw e}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
