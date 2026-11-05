/* Continuous real X11 screen + isolated browser audio capture. No mocked UI/media. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn, execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'deliverables');
const base = process.env.APP_URL || 'http://127.0.0.1:8767';
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
    await at(0,'开始页：原创合成旁白样例，规则建议');
    await at(8,'打开现有样例');
    const created=page.waitForResponse(r=>r.url().endsWith('/from-sample'));await click('[data-action="start-sample"]');project=await(await created).json();
    await page.locator('#source-video').waitFor();
    await at(14,'实际播放原片与字幕');await play(1);
    await at(22,'点击第三段文字定位原片');await pause();await click('[data-action="seek"][data-id="s03"]');await play(project.blocks[2].clipStartFrame/30);
    await at(28,'确认条件、否定和数字片段必留');await pause();
    for(const id of ['s03','s04','s05']) {await act(`[data-action="lock"][data-id="${id}"]`);await delay(1200);}
    await at(35,'目标30秒：必留35.267秒，展示真实冲突');await act('[data-action="set-preset"][data-seconds="30"]');await page.evaluate(()=>scrollTo(0,0));
    await at(42,'调回90秒并生成规则建议');await act('[data-action="set-preset"][data-seconds="90"]');await click('[data-action="propose"]');await page.locator('[data-action="apply-proposal"]').waitFor();
    await page.locator('.proposal-panel').scrollIntoViewIfNeeded();
    await at(54,'查看理由后应用，保守建议仍超过目标');await act('[data-action="apply-proposal"]');await page.evaluate(()=>scrollTo(0,0));
    await at(61,'人工确认删除重复与次要内容');
    for(const id of ['s02','s08','s13','s11']) {if(project.edit.keptBlockIds.includes(id)) {await act(`[data-action="delete"][data-id="${id}"]`);await delay(1800);}}
    assert(project.metrics.plannedDurationMs<=90000);
    await at(76,'恢复一段并撤销，选择可逆');await act('[data-action="restore"][data-id="s02"]');await delay(3000);await act('[data-action="undo"]');await page.evaluate(()=>scrollTo(0,0));
    await at(87,'生成实际短片；保留完整渲染等待');await click('[data-action="render"]');
    await page.locator('#result-video').waitFor({timeout:300000});
    const readyAt=(Date.now()-start)/1000;console.log('Actual render ready',readyAt);
    assert(readyAt<112,'Render exceeded walkthrough timing; do not claim a 2–3 minute recording');
    await at(102,'播放成片，跨过第一处删减切口');await play(7);
    await at(114,'继续播放另一处切口和同步字幕');await pause();await play(43);
    await at(124,'下载同一次剪辑的MP4、SRT和删减记录');await pause();
    const downloads={};
    for(const [kind,name] of [['mp4','walkthrough_download.mp4'],['srt','walkthrough_download.srt'],['record','walkthrough_download_record.json']]) {
      const pending=page.waitForEvent('download');await click(`[data-download="${kind}"]`);const download=await pending;
      assert.equal(await download.failure(),null);await download.saveAs(path.join(out,name));downloads[kind]=name;await delay(1200);
    }
    await at(136,'恢复片段后，上一版文件不可作为当前结果下载');await click('[data-action="back-editor"]');await act('[data-action="restore"][data-id="s02"]');await click('[data-action="show-result"]');
    await page.getByText('这是上一版短片',{exact:true}).waitFor();assert.equal(await page.locator('[data-download]').count(),0);
    await at(147,'返回撤销恢复，再次生成当前版本');await click('[data-action="back-editor"]');await act('[data-action="undo"]');await click('[data-action="render"]');await page.locator('#result-video').waitFor({timeout:300000});
    await at(160,'最终真实成片：77.988秒，规则建议加人工确认');await play(7);
    await at(170,'演示结束');await pause();
    recorder.stdin.write('q\n');await recordingDone;recorder=null;
    // Normalize captured device timestamps; copy the original video bitstream unchanged.
    const rawCapture=path.join(root,'data/browser_acceptance/raw_walkthrough.mp4');
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
    const result={recordedAt:new Date().toISOString(),baseUrl:base,browser:await browser.version(),durationSeconds:duration,capturedFrames:Number(video.nb_frames),meanVolumeDb,method:'Continuous Xvfb desktop capture with FFmpeg x11grab + isolated PulseAudio sink monitor; no cuts or intentional speed changes; captured audio timestamps normalized with aresample; original video bitstream copied',audio:'Actual browser source/result playback; no microphone narration or replacement soundtrack',video:'walkthrough.mp4',projectId:project.id,finalPlannedDurationMs:project.metrics.plannedDurationMs,renderReadyAtSeconds:readyAt,steps,downloads};
    fs.writeFileSync(path.join(out,'recording_validation.json'),JSON.stringify(result,null,2)+'\n');
  } finally {
    if(recorder && recorder.exitCode===null){recorder.stdin.write('q\n');await recordingDone.catch(()=>{});}
    if(browser)await browser.close();
    if(log!==undefined)fs.closeSync(log);
    execFileSync('pactl',['unload-module',moduleId],{env:{...process.env,DISPLAY:''}});
    if(desktop && desktop.exitCode===null)desktop.kill('SIGTERM');
  }
})().catch(e=>{console.error(e);process.exitCode=1});
