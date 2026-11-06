/* Continuous real X11 screen + isolated browser audio capture. No mocked UI/media. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn, execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'deliverables/v2');
const base = process.env.APP_URL || 'http://127.0.0.1:8770';
assert(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
let display;
let desktop;
const xvfb = process.env.XVFB_EXECUTABLE || 'Xvfb';
const sink = 'koubo_recording_' + process.pid;
const steps = [];
const delay = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  desktop = spawn(xvfb, ['-displayfd', '1', '-screen', '0', '1440x1000x24', '-nolisten', 'tcp'], {stdio:['ignore','pipe','pipe']});
  display = await new Promise((resolve,reject) => {
    let output='';
    desktop.stdout.on('data', b => { output+=b.toString(); const m=output.match(/^([0-9]+)$/m);if(m)resolve(':'+m[1]); });
    desktop.once('error',reject);desktop.once('exit',code=>reject(new Error('Xvfb exit '+code)));
  });
  const moduleId = execFileSync('pactl', ['load-module', 'module-null-sink', `sink_name=${sink}`, 'rate=48000'], { env: { ...process.env, DISPLAY: '' } }).toString().trim();
  let browser, recorder, recordingDone, log;
  try {
    browser = await chromium.launch({ headless: false, executablePath: process.env.CHROME_EXECUTABLE,
      ignoreDefaultArgs: ['--mute-audio', '--enable-automation'], args: ['--window-size=1440,1000', '--window-position=0,0', '--autoplay-policy=no-user-gesture-required'],
      env: { ...process.env, DISPLAY: display, PULSE_SINK: sink } });
    const context = await browser.newContext({ viewport: null, acceptDownloads: true });
    const page = await context.newPage();
    await page.goto(base); await page.locator('[data-action="start-sample"]').waitFor();
    const cdp = await context.newCDPSession(page);
    const { windowId } = await cdp.send('Browser.getWindowForTarget');
    await cdp.send('Browser.setWindowBounds', { windowId, bounds: { left: 0, top: 0, width: 1440, height: 1000, windowState: 'normal' } });
    await delay(1000);
    const screen = await page.evaluate(() => ({width:innerWidth,height:innerHeight}));
    assert(screen.width >= 1400 && screen.height >= 850, JSON.stringify(screen));
    log = fs.openSync(path.join(out, 'recording_ffmpeg.log'), 'w');
    recorder = spawn('ffmpeg', ['-y','-hide_banner','-thread_queue_size','1024','-f','x11grab','-framerate','25',
      '-video_size','1440x1000','-draw_mouse','1','-i',display+'.0','-thread_queue_size','1024',
      '-f','pulse','-i',sink+'.monitor','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p',
      '-c:a','aac','-b:a','160k','-ar','48000','-ac','2','-movflags','+faststart',
      path.join(out, 'walkthrough.mp4')], { stdio: ['pipe', 'ignore', log], env: {...process.env, DISPLAY: display} });
    recordingDone = new Promise((resolve, reject) => { recorder.once('exit', code => code === 0 ? resolve() : reject(new Error('FFmpeg exit ' + code))); recorder.once('error', reject); });
    // Start the action clock once capture is writing frames; no startup frames are removed.
    let captureReady=false;
    for(let i=0;i<100;i++) {
      const frames=[...fs.readFileSync(path.join(out,'recording_ffmpeg.log'),'utf8').matchAll(/frame=\s*(\d+)/g)];
      if(frames.length && Number(frames[frames.length-1][1])>=25) {captureReady=true;break;}
      if(recorder.exitCode !== null) throw new Error('Capture failed before first frame');
      await delay(100);
    }
    assert(captureReady, 'Capture did not produce 25 real frames within 10 seconds');
    const start = Date.now();
    let project;
    async function at(second, text) {
      await delay(Math.max(0, start + second * 1000 - Date.now()));
      const elapsed = (Date.now() - start) / 1000;
      steps.push({second:elapsed,text}); console.log(elapsed.toFixed(1),text);
    }
    async function click(selector) { const l=page.locator(selector).first();await l.scrollIntoViewIfNeeded();await l.hover();await delay(300);await l.click(); }
    async function act(selector) {
      const [r] = await Promise.all([page.waitForResponse(r=>r.url().endsWith('/actions')&&r.request().method()==='POST'), click(selector)]);
      assert.equal(r.status(),200);project=await r.json();
      await page.waitForFunction(()=>document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
    }
    async function play(time) {await page.locator('video').scrollIntoViewIfNeeded();await page.locator('video').evaluate((v,t)=>{v.currentTime=t;return v.play()},time);}
    async function pause() {await page.locator('video').evaluate(v=>v.pause());}
    await at(0,'真人样例与无字幕导入入口');
    await page.locator('#sample-picker').selectOption('real_ying_v2');
    await at(6,'打开公开授权真人样例');
    const created=page.waitForResponse(r=>r.url().endsWith('/from-sample'));await click('[data-action="start-sample"]');project=await(await created).json();
    await page.locator('#source-video').waitFor();await play(1);
    await at(16,'导入真实视频片段，不提供SRT');await pause();await click('[data-action="new-project"]');
    await page.locator('input[name="video"]').setInputFiles({name:'真人语言分享片段.mp4',mimeType:'video/mp4',buffer:fs.readFileSync(path.join(root,'data/v2_sources/ying_import_18.mp4'))});
    const imported=page.waitForResponse(r=>r.url().endsWith('/import'));await click('#import-form button[type="submit"]');project=await(await imported).json();
    await page.locator('#source-video').waitFor({timeout:600000});
    project=await context.request.get(base+'/api/projects/'+project.id).then(r=>r.json());
    await at(40,'自动字幕已生成，打开精修面板');
    const correct=project.blocks.find(b=>b.text.includes('访宴'))||project.blocks[0];
    await click(`[data-action="refine"][data-id="${correct.id}"]`);
    await page.locator('#caption-text').fill(correct.text.replaceAll('访宴','方言'));
    await act('#caption-edit-form button:not([type])');
    await page.locator('#note-text').fill('回听后确认方言、地名等转写内容。');await act('#note-form button:not([type])');
    await at(52,'在另一段中按实测时间剪词');await click('[data-action="close-refine"]');
    const word=project.words.find(w=>w.blockId!==correct.id&&['很','呢','其实','啊'].includes(w.text.trim()))||project.words.find(w=>w.blockId!==correct.id);
    await click(`[data-action="refine"][data-id="${word.blockId}"]`);await click(`[data-action="select-word"][data-word="${word.id}"]`);
    await act('[data-action="delete-selected-words"]');await delay(2000);await act('[data-action="restore-selected-words"]');
    await at(65,'整句移动，音视频和字幕按同一顺序调整');
    await act(`[data-action="move-down"][data-id="${word.blockId}"]`);await click('[data-action="close-refine"]');await act('[data-action="undo"]');
    await at(75,'设置10秒目标并请求本地模型建议');
    await page.locator('#target-seconds').fill('10');await act('#target-form button');
    const requested=page.waitForResponse(r=>r.url().endsWith('/processing/suggestions'));await click('[data-action="propose"]');const pj=await(await requested).json();
    let proposed;const deadline=Date.now()+240000;
    do{proposed=await context.request.get(base+'/api/processing-jobs/'+pj.id).then(r=>r.json());if(!['queued','running'].includes(proposed.status))break;await delay(1000)}while(Date.now()<deadline);
    assert.equal(proposed.status,'succeeded');assert.equal(proposed.result.source,'local_llm');
    await page.locator('.proposal-v2').waitFor();await page.locator('.proposal-v2').scrollIntoViewIfNeeded();
    await at(110,'查看整体方针和逐项理由，确认其中一项');
    await page.screenshot({path:path.join(out,'acceptance/10_local_suggestions.png'),fullPage:true});
    const item=proposed.result.items.find(i=>i.type!=='rewrite');
    if(item){const accepted=page.waitForResponse(r=>r.url().endsWith('/proposal-decisions'));await click(`[data-action="accept-item"][data-item="${item.id}"]`);project=(await(await accepted).json()).project;}
    await at(123,'人工确认保留内容，使时长达到目标');
    for(const block of [...project.blocks].reverse()){
      if(project.metrics.plannedDurationMs<=10000)break;
      if(project.edit.keptBlockIds.includes(block.id)&&project.edit.keptBlockIds.length>1)await act(`[data-action="delete"][data-id="${block.id}"]`);
    }
    await page.evaluate(()=>scrollTo(0,0));
    await at(137,'生成实际MP4，保留真实渲染等待');
    if(project.metrics.plannedDurationMs>10000)await page.locator('#allow-over').check();
    await click('[data-action="render"]');await page.locator('#result-video').waitFor({timeout:300000});
    const readyAt=(Date.now()-start)/1000;
    await at(150,'播放实际精简结果和同步字幕');await play(.2);
    await at(157,'下载MP4、SRT和可交接ZIP');await pause();
    const downloads={};
    for(const [kind,name]of [['mp4','walkthrough_download.mp4'],['srt','walkthrough_download.srt'],['bundle','walkthrough_handoff.zip']]){
      const pending=page.waitForEvent('download');await click(`[data-download="${kind}"]`);const d=await pending;await d.saveAs(path.join(out,name));downloads[kind]=name;
    }
    await at(169,'流程完成：真人素材、真实识别、真实模型建议与导出');
    recorder.stdin.write('q\n');await recordingDone;recorder=null;
    // Normalize captured device timestamps; copy the original video bitstream unchanged.
    const rawCapture=path.join(root,'data/v2_recording/raw_walkthrough.mp4');
    fs.mkdirSync(path.dirname(rawCapture),{recursive:true});
    fs.renameSync(path.join(out,'walkthrough.mp4'),rawCapture);
    execFileSync('ffmpeg',['-v','error','-i',rawCapture,'-c:v','copy','-af','aresample=async=1000:first_pts=0',
      '-c:a','aac','-ar','48000','-b:a','160k','-movflags','+faststart','-y',path.join(out,'walkthrough.mp4')]);
    const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-of','json',path.join(out,'walkthrough.mp4')]).toString());
    const duration=Number(probe.format.duration);
    const video=probe.streams.find(s=>s.codec_type==='video');
    assert(duration>=120 && duration<=180, 'Recording duration: '+duration);
    assert(Number(video.nb_frames)>=duration*20, 'Insufficient captured frames');
    const volumeRun=spawnSync('ffmpeg',['-hide_banner','-i',path.join(out,'walkthrough.mp4'),'-af','volumedetect','-f','null','-'],{encoding:'utf8'});
    assert.equal(volumeRun.status,0);
    const meanVolumeDb=Number(volumeRun.stderr.match(/mean_volume: ([\d.-]+) dB/)[1]);
    assert(meanVolumeDb>-60, 'Recording contains no usable playback sound');
    const result={sourceCredit:'Wikitongues, Ying Li; CC BY-SA 4.0; licensed 18-second excerpt, transcoded and edited; no endorsement',recordedAt:new Date().toISOString(),baseUrl:base,browser:await browser.version(),durationSeconds:duration,capturedFrames:Number(video.nb_frames),meanVolumeDb,method:'Continuous Xvfb desktop capture with FFmpeg x11grab + isolated PulseAudio sink monitor; no cuts or intentional speed changes; captured audio timestamps normalized with aresample; original video bitstream copied',audio:'Actual browser source/result playback; no microphone narration or replacement soundtrack',video:'walkthrough.mp4',projectId:project.id,finalPlannedDurationMs:project.metrics.plannedDurationMs,renderReadyAtSeconds:readyAt,steps,downloads};
    fs.writeFileSync(path.join(out,'recording_validation.json'),JSON.stringify(result,null,2)+'\n');
  } finally {
    if(recorder && recorder.exitCode===null){recorder.stdin.write('q\n');await recordingDone.catch(()=>{});}
    if(browser)await browser.close();
    if(log!==undefined)fs.closeSync(log);
    execFileSync('pactl',['unload-module',moduleId],{env:{...process.env,DISPLAY:''}});
    if(desktop && desktop.exitCode===null)desktop.kill('SIGTERM');
  }
})().catch(e=>{console.error(e);process.exitCode=1});
