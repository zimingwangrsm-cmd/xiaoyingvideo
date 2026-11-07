/* Final-version continuous X11/browser-audio recording. Real precomputed Qwen proposal;
   fixture microphone and one deliberately aborted HTTP request are disclosed on screen. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn,spawnSync,execFileSync}=require('node:child_process');const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'deliverables/final_submission'),base=process.env.APP_URL||'http://127.0.0.1:8779';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const meta=JSON.parse(fs.readFileSync(path.join(root,'data/final_demo_private.json'))),inference=JSON.parse(fs.readFileSync(path.join(out,'real_inference.json')));
 const desktop=spawn(process.env.XVFB_EXECUTABLE||'Xvfb',['-displayfd','1','-screen','0','1440x1000x24','-nolisten','tcp'],{stdio:['ignore','pipe','pipe']});
 const display=await new Promise((resolve,reject)=>{let s='';desktop.stdout.on('data',b=>{s+=b;const m=s.match(/^(\d+)$/m);if(m)resolve(':'+m[1])});desktop.once('error',reject)});
 const sink='koubo_final_'+process.pid,moduleId=execFileSync('pactl',['load-module','module-null-sink',`sink_name=${sink}`,'rate=48000'],{env:{...process.env,DISPLAY:''}}).toString().trim();let browser,recorder,done,fd;const steps=[],errors=[];
 try{
  browser=await chromium.launch({headless:false,executablePath:process.env.CHROME_EXECUTABLE,ignoreDefaultArgs:['--mute-audio','--enable-automation'],args:['--window-size=1440,1000','--window-position=0,0','--autoplay-policy=no-user-gesture-required','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+path.join(root,'data/final_microphone_input.wav')],env:{...process.env,DISPLAY:display,PULSE_SINK:sink}});
  const c=await browser.newContext({viewport:null,acceptDownloads:true,permissions:['microphone'],storageState:path.join(root,'data/final_demo_storage.json')});const page=await c.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.locator('#proposal-v2').waitFor();
  let p=await c.request.get(base+'/api/projects/'+meta.projectId).then(r=>r.json());
  const click=async selector=>{const el=page.locator(selector).first();await el.scrollIntoViewIfNeeded();await el.hover();await delay(120);await el.click()};
  async function act(selector){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')),click(selector)]);assert.equal(r.status(),200);p=await r.json();await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'))}
  await click('[data-action="workspace-tab"][data-tab="transcript"]');await page.evaluate(()=>scrollTo(0,0));
  await page.evaluate(()=>{const note=document.createElement('div');note.id='recording-disclosure';note.style.cssText='position:fixed;top:0;left:0;width:100%;z-index:999999;background:#143d43;color:white;font:14px/1.6 sans-serif;padding:9px 18px;pointer-events:none;box-sizing:border-box';document.body.append(note)});
  async function caption(text){await page.locator('#recording-disclosure').evaluate((e,t)=>e.textContent='录屏说明｜'+t,text)}
  await caption('同版本实际操作；本地模型已提前完成推理 '+inference.backendElapsedSeconds+' 秒，下面从审核候选开始。');
  fd=fs.openSync(path.join(root,'data/final_recording_ffmpeg.log'),'w');
  recorder=spawn('ffmpeg',['-y','-hide_banner','-thread_queue_size','1024','-f','x11grab','-framerate','25','-video_size','1440x1000','-draw_mouse','1','-i',display+'.0','-thread_queue_size','1024','-f','pulse','-i',sink+'.monitor','-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-movflags','+faststart',path.join(out,'demo_walkthrough.mp4')],{stdio:['pipe','ignore',fd],env:{...process.env,DISPLAY:display}});
  done=new Promise((resolve,reject)=>{recorder.once('exit',code=>code===0?resolve():reject(new Error('FFmpeg '+code)));recorder.once('error',reject)});
  await delay(1500);const start=Date.now();
  async function at(second,text){await delay(Math.max(0,start+second*1000-Date.now()));steps.push({second:(Date.now()-start)/1000,text});console.log(steps.at(-1).second.toFixed(1),text);await caption(text)}
  await at(0,'任务：把128秒语言分享整理成一分钟内简介；主线和必留由用户确定。模型推理 '+inference.backendElapsedSeconds+' 秒已提前完成。');
  await page.locator('#source-video').evaluate(v=>{v.currentTime=1;return v.play()});await delay(8000);await page.locator('#source-video').evaluate(v=>v.pause());
  await at(16,'查看真实Qwen建议和理由；确认前不会修改视频。推理等待未纳入本段连续录屏。');await click('[data-action="workspace-tab"][data-tab="suggestions"]');await click('#proposal-strategy summary');await delay(4000);await click('#proposal-strategy summary');
  const proposal=JSON.parse(fs.readFileSync(path.join(out,'real_inference.json'))).proposal;assert(proposal.items.length>=3);
  await at(28,'接受一项、拒绝一项，再确认其余待处理建议；每项操作都经过版本和必留校验。');
  for(const [action,id] of [['accept-item',proposal.items[0].id],['reject-item',proposal.items[1].id]]){const [r]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/proposal-decisions')),click(`[data-action="${action}"][data-item="${id}"]`)]);assert.equal(r.status(),200);p=(await r.json()).project;await delay(2000)}
  const [accepted]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/proposal-decisions')),click('[data-action="accept-all"]')]);assert.equal(accepted.status(),200);p=(await accepted.json()).project;
  await click('[data-action="proposal-filter"][data-filter="rejected"]');await delay(2500);
  await at(45,'返回文稿，手动删一句后撤销；系统保留作者对内容的最终控制。');await click('[data-action="workspace-tab"][data-tab="transcript"]');
  const editable=p.edit.keptBlockIds.find(id=>!p.edit.lockedBlockIds.includes(id));assert(editable);await act(`[data-action="delete"][data-id="${editable}"]`);await delay(2500);await act('[data-action="undo"]');
  await at(60,'补录演示使用授权样例的测试麦克风输入，不是本人真人新录；支持上传或直接录音，每句最多60秒。');
  await click('[data-action="record-line"][data-id="s01"]');if(p.edit.lockedBlockIds.includes('s01'))await act('.refine-panel [data-action="unlock"]');
  await click('[data-action="start-recording"]');await page.locator('#recording-timer').waitFor();await delay(4000);await click('[data-action="stop-recording"]');await page.locator('#take-audio').waitFor();await page.locator('#take-audio').evaluate(a=>a.play());await delay(3500);await page.locator('#take-audio').evaluate(a=>a.pause());
  await page.screenshot({path:path.join(out,'screenshots/05-sentence-recording.png')});
  await at(80,'试听后提交真实本地识别，再确认替换；修改字幕与修改声音是不同操作。');await click('#recording-form button:not([type])');await page.locator('[data-action="confirm-recording"]').waitFor({timeout:120000});await click('[data-action="confirm-recording"]');await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
  await click('[data-action="record-line"][data-id="s01"]');await act('[data-action="restore-audio"]');await click('[data-action="close-refine"]');
  await at(105,'测试补录已恢复原声。现在模拟一次网络请求中断：编辑仍保留，重试后继续生成。');
  await page.route('**/renders',route=>route.abort('connectionfailed'),{times:1});await click('[data-action="render"]');await page.locator('[data-action="retry-operation"]').waitFor();await page.locator('[data-action="retry-operation"]').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'screenshots/06-failure-retry.png')});await delay(3000);await page.unroute('**/renders');await click('[data-action="retry-operation"]');
  await page.locator('#result-video').waitFor({timeout:120000});if(await page.locator('[data-action="ack-render"]').count()){await page.locator('#allow-over').check();await click('[data-action="ack-render"]')}
  await at(130,'真实渲染完成；播放结果并检查切口。专名字幕仍待作者核对，渲染成功不等于质量听审通过。');
  await page.locator('#result-video').evaluate(v=>{v.currentTime=0;return v.play()});await delay(12000);await page.locator('#result-video').evaluate(v=>v.pause());await click('[data-action="loop-cut"]');await delay(4000);await click('[data-action="stop-cut"]');await page.screenshot({path:path.join(out,'screenshots/07-result.png')});
  await at(149,'下载真实MP4、同步SRT与编辑记录；这些文件属于同一次编辑快照。');
  for(const [kind,name] of [['mp4','demo_result.mp4'],['srt','demo_result.srt'],['record','demo_edit_record.json']]){const event=page.waitForEvent('download');await click(`[data-download="${kind}"]`);await(await event).saveAs(path.join(out,name))}
  await at(158,'下载后继续修改，旧成片会标为上一版，防止下载与当前选择不一致的结果。');await click('[data-action="back-editor"]');p=await c.request.get(base+'/api/projects/'+meta.projectId).then(r=>r.json());const remaining=p.edit.keptBlockIds.find(id=>!p.edit.lockedBlockIds.includes(id));await act(`[data-action="delete"][data-id="${remaining}"]`);await click('[data-action="show-result"]');await page.screenshot({path:path.join(out,'screenshots/08-stale-result.png')});assert.equal(await page.locator('[data-download="mp4"]').count(),0);
  await at(170,'演示结束：目标、确认、补录、失败恢复与真实输出已连通；最终内容仍由作者审阅。');
  recorder.stdin.write('q\n');await done;recorder=null;assert.deepEqual(errors,[]);
  const file=path.join(out,'demo_walkthrough.mp4'),info=JSON.parse(execFileSync('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',file]));const duration=Number(info.format.duration),video=info.streams.find(s=>s.codec_type==='video');assert(duration>=120&&duration<=180&&Number(video.nb_read_frames)>3000);
  const volume=spawnSync('ffmpeg',['-hide_banner','-i',file,'-af','volumedetect','-vn','-sn','-f','null','-'],{encoding:'utf8'});const mean=Number(volume.stderr.match(/mean_volume: ([\d.-]+) dB/)?.[1]);assert(Number.isFinite(mean)&&mean>-50);
  fs.writeFileSync(path.join(out,'recording_validation.json'),JSON.stringify({applicationCommit:'fce60bfcbaf96a4b2574bc6b582753d0561f4424',durationSeconds:duration,frames:Number(video.nb_read_frames),meanVolumeDb:mean,steps,pageErrors:errors,method:'Continuous X11 desktop + actual browser playback audio, no speed changes or montage. On-screen explanatory banner. Real model proposal prepared before recording; elapsed inference disclosed. Fixture microphone; one browser-aborted network request for failure recovery; server fault injection disabled.'},null,2)+'\n');console.log('PASS final continuous recording',duration,'seconds',mean,'dB');
 }finally{if(recorder){recorder.stdin.write('q\n');await done.catch(()=>{})}if(browser)await browser.close();if(fd)fs.closeSync(fd);execFileSync('pactl',['unload-module',moduleId],{env:{...process.env,DISPLAY:''}});desktop.kill('SIGTERM')}
})().catch(e=>{console.error(e);process.exitCode=1});
