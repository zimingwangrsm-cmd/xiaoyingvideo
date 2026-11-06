const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),out=path.join(root,'deliverables/optimization');fs.mkdirSync(out,{recursive:true});
const base=process.env.APP_URL||'http://127.0.0.1:8772',data=process.env.TEST_DATA_DIR||path.join(root,'data/optimization_acceptance');
const checks=[],errors=[];const pass=(name,kind='real HTTP/browser')=>{checks.push({name,kind});console.log('PASS',name)};
(async()=>{
 const browser=await chromium.launch({headless:true,args:["--disable-audio-output"],executablePath:process.env.CHROME_EXECUTABLE});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));let p;
 async function sample(id='interview_intro_v1'){
  await page.locator('#sample-picker').selectOption(id);const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/from-sample')),page.locator('[data-action="start-sample"]').click()]);p=await r.json();await page.locator('#source-video').waitFor();
 }
 async function save(form){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')),page.locator(form+' button:not([type])').click()]);assert.equal(r.status(),200);p=await r.json();await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));}
 async function action(selector){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')),page.locator(selector).first().click()]);assert.equal(r.status(),200);p=await r.json();await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));}
 try{
  await page.goto(base);await sample();const a=p.id;
  await page.locator('[data-action="refine"][data-id="s01"]').click();
  await page.locator('#caption-text').fill('字幕校对甲。');await page.locator('#note-text').fill('项目A尚未保存的备注');await save('#caption-edit-form');
  assert.equal(await page.locator('#note-text').inputValue(),'项目A尚未保存的备注');pass('saving caption preserves unsaved note');
  await page.route('**/actions',route=>route.abort('connectionfailed'),{times:1});
  await page.locator('#caption-text').fill('断网后仍要保留的字幕。');await page.locator('#caption-edit-form button:not([type])').click();
  await page.locator('[data-action="retry-operation"]').waitFor();assert.equal(await page.locator('#caption-text').inputValue(),'断网后仍要保留的字幕。');pass('failed request preserves all field input','injected network failure; real DOM');
  await page.unroute('**/actions');
  let entered;const waiting=new Promise(r=>entered=r);
  await page.route('**/actions',async route=>{const response=await route.fetch();entered();await new Promise(r=>setTimeout(r,700));await route.fulfill({response})},{times:1});
  await page.locator('#caption-text').fill('已发送的版本。');const response=page.waitForResponse(r=>r.url().endsWith('/actions'));
  await page.locator('#caption-edit-form button:not([type])').click();await waiting;await page.locator('#caption-text').fill('等待响应时的新输入。');await response;
  await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  assert.equal(await page.locator('#caption-text').inputValue(),'等待响应时的新输入。');pass('late successful response preserves subsequent typing','delayed real HTTP response');
  await page.unroute('**/actions');await page.keyboard.press('Escape');assert.equal(await page.locator('.refine-panel').count(),0);
  assert.equal(await page.evaluate(()=>document.activeElement.dataset.action),'refine');pass('Escape closes drawer and restores trigger focus');
  await page.locator('[data-action="new-project"]').click();await sample();
  await page.locator('[data-action="refine"][data-id="s01"]').click();assert.equal(await page.locator('#note-text').inputValue(),'');
  await page.locator('#note-text').fill('项目B备注');await save('#note-form');
  await page.locator('[data-action="close-refine"]').click();await page.locator('[data-action="new-project"]').click();
  await page.locator('#recent-project').selectOption(a);await page.locator('[data-action="resume-recent"]').click();await page.locator('#source-video').waitFor();
  await page.locator('[data-action="refine"][data-id="s01"]').click();assert.equal(await page.locator('#note-text').inputValue(),'项目A尚未保存的备注');
  await page.keyboard.press('Shift+Tab');assert(await page.evaluate(()=>document.querySelector('.refine-panel').contains(document.activeElement)));
  await page.screenshot({path:path.join(out,'drafts-and-tabs.png')});pass('cross-project draft isolation, return navigation and focus trap');
  await page.locator('[data-action="discard-drafts"]').click();await page.locator('[data-action="close-refine"]').click();
  // Deterministic multi-item proposals, explicitly NOT counted as real-model inference.
  p=await context.request.get(base+'/api/projects/'+a).then(r=>r.json());const proposalId=crypto.randomBytes(16).toString('hex'),jid=crypto.randomBytes(16).toString('hex');
  const items=['s02','s03','s04','s05'].map((bid,i)=>({id:'i0'+(i+1),blockId:bid,type:'delete_block',before:p.blocks.find(b=>b.id===bid).text,after:'测试删除',reason:'确定性交互用例',status:'pending',action:{type:'delete',blockIds:[bid]},durationDeltaMs:0}));
  const fixture={id:proposalId,projectId:a,baseRevision:p.revision,source:'rules',strategy:'确定性多项交互测试，不代表模型质量',items,currentDurationMs:p.metrics.plannedDurationMs,estimatedDurationMs:p.metrics.plannedDurationMs};
  const folder=path.join(data,'projects',a,'proposals_v2');fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,proposalId+'.json'),JSON.stringify(fixture));
  await page.route('**/processing/suggestions',route=>route.fulfill({status:202,contentType:'application/json',body:JSON.stringify({id:jid,projectId:a,status:'queued',kind:'suggestions'})}));
  await page.route('**/processing-jobs/'+jid,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:jid,projectId:a,kind:'suggestions',status:'succeeded',phase:'done',baseRevision:p.revision,result:fixture})}));
  await page.locator('[data-action="propose"]').first().click();await page.locator('[data-action="accept-item"]').first().waitFor();
  for(const selector of ['[data-action="accept-item"][data-item="i01"]','[data-action="reject-item"][data-item="i02"]','[data-action="accept-all"]']){
   const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/proposal-decisions')),page.locator(selector).click()]);assert.equal(r.status(),200);const result=await r.json();p=result.project;
  }
  assert(!p.edit.keptBlockIds.includes('s02'));assert(p.edit.keptBlockIds.includes('s03'));assert(!p.edit.keptBlockIds.includes('s04'));assert(!p.edit.keptBlockIds.includes('s05'));
  pass('accept one, reject another, and accept remaining multiple items','deterministic proposal fixture + real decision HTTP');
  await page.unrouteAll();await context.close();
  const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,acceptDownloads:true});const m=await mobile.newPage();m.on('pageerror',e=>errors.push(e.message));
  await m.goto(base);await m.locator('#sample-picker').selectOption('real_tao_v2');
  const [created]=await Promise.all([m.waitForResponse(r=>r.url().endsWith('/from-sample')),m.locator('[data-action="start-sample"]').click()]);let mp=await created.json();
  if(mp.edit.lockedBlockIds.includes('s01')){await m.locator('[data-action="unlock"][data-id="s01"]').click();await m.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));}
  await m.locator('[data-action="refine"][data-id="s01"]').click();await m.locator('#note-text').fill('移动端备注');
  await m.setViewportSize({width:390,height:480});await m.locator('#note-form button:not([type])').click();await m.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  await m.locator('[data-action="refine-tab"][data-tab="cut"]').click();await m.locator('.word-chip').first().click();
  const [corrected]=await Promise.all([m.waitForResponse(r=>r.url().endsWith('/actions')),m.locator('#word-text').fill('大家好，').then(()=>m.locator('#word-edit-form button:not([type])').click())]);assert.equal(corrected.status(),200);
  await m.locator('[data-action="delete-selected-words"]').click();await m.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  await m.locator('[data-action="restore-selected-words"]').click();await m.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  await m.locator('[data-action="close-refine"]').click();await m.locator('[data-action="set-preset"][data-seconds="60"]').click();await m.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));await m.locator('[data-action="refine"][data-id="s01"]').click();
  await m.locator('[data-action="refine-tab"][data-tab="audio"]').click();await m.locator('input[name="recording"]').setInputFiles(path.join(root,'data/v2_sources/replacement_excerpt.wav'));
  const [uploaded]=await Promise.all([m.waitForResponse(r=>r.url().endsWith('/recordings')&&r.request().method()==='POST'),m.locator('#recording-form button:not([type])').click()]);assert.equal(uploaded.status(),202);const job=await uploaded.json();
  assert.equal(job.intent.blockId,'s01');await m.locator('[data-action="confirm-recording"]').waitFor({timeout:180000});
  await mobile.storageState({path:path.join(root,'data/optimization_mobile_debug.json')});
  await m.locator('.processing-card audio').evaluate(a=>{window.audioBefore=a;window.audioEvents=[];for(const type of ['pause','emptied','loadstart','ended'])a.addEventListener(type,()=>window.audioEvents.push([type,a.currentTime]));return a.play();});await m.waitForTimeout(500);const before=await m.locator('.processing-card audio').evaluate(a=>a.currentTime);
  // A redraw from changing the target must preserve the playing audio element.
  await m.locator('[data-action="set-preset"][data-seconds="60"]').click();await m.waitForTimeout(500);
  console.log('AUDIO',before,await m.locator('.processing-card audio').evaluate(a=>({same:a===window.audioBefore,time:a.currentTime,paused:a.paused,duration:a.duration,events:window.audioEvents})));
  assert(await m.locator('.processing-card audio').evaluate(a=>a.currentTime)>before);
  await m.locator('.processing-card audio').evaluate(a=>a.pause());await m.locator('[data-action="confirm-recording"]').click();
  await m.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  await m.setViewportSize({width:390,height:844});
  // This is a workflow check, not a product-quality short film: keep a few actual clips for render/cut audition.
  mp=await mobile.request.get(base+'/api/projects/'+mp.id).then(r=>r.json());
  for(const b of mp.blocks){if(['s01','s03','s05'].includes(b.id))continue;const [r]=await Promise.all([m.waitForResponse(r=>r.url().endsWith('/actions')),m.locator(`[data-action="delete"][data-id="${b.id}"]`).click()]);assert.equal(r.status(),200);}
  await m.locator('[data-action="render"]').click();await m.locator('#result-video').waitFor({timeout:180000});await m.locator('[data-action="loop-cut"]').click();
  await m.waitForTimeout(3500);assert(await m.locator('#result-video').evaluate(v=>!v.paused));await m.locator('[data-action="stop-cut"]').click();
  const event=m.waitForEvent('download');await m.locator('[data-download="mp4"]').click();await(await event).saveAs(path.join(out,'mobile_workflow.mp4'));
  await m.screenshot({path:path.join(out,'mobile-complete.png'),fullPage:true});assert(await m.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  pass('mobile correction, word cut/restore, recording, audio persistence, real render, cut-loop and download','real Chromium mobile emulation with virtual audio clock; keyboard space simulated by viewport resize, not physical-device or human-listening proof');
  await mobile.close();assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'browser_validation.json'),JSON.stringify({testedAt:new Date().toISOString(),checks,pageErrors:errors},null,2)+'\n');
 }catch(e){if(!page.isClosed())await page.screenshot({path:path.join(out,'browser_failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'browser_failure.json'),JSON.stringify({checks,error:e.stack,errors},null,2));throw e;}
 finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
