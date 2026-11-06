/* Real X11 + browser audio recording of the already generated AI result, not the inference wait. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn,spawnSync,execFileSync}=require('node:child_process');const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'deliverables/optimization'),base=process.env.APP_URL||'http://127.0.0.1:8774';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const privateState=JSON.parse(fs.readFileSync(path.join(root,'data/showcase_project_private.json')));
 const xvfb=spawn(process.env.XVFB_EXECUTABLE||'Xvfb',['-displayfd','1','-screen','0','1440x1000x24','-nolisten','tcp'],{stdio:['ignore','pipe','pipe']});
 const display=await new Promise((resolve,reject)=>{let s='';xvfb.stdout.on('data',b=>{s+=b;const m=s.match(/^(\d+)$/m);if(m)resolve(':'+m[1])});xvfb.once('error',reject)});
 const sink='koubo_opt_'+process.pid;const moduleId=execFileSync('pactl',['load-module','module-null-sink',`sink_name=${sink}`,'rate=48000'],{env:{...process.env,DISPLAY:''}}).toString().trim();let browser,recorder,done,fd;
 try{
  browser=await chromium.launch({headless:false,executablePath:process.env.CHROME_EXECUTABLE,ignoreDefaultArgs:['--mute-audio','--enable-automation'],args:['--window-size=1440,1000','--window-position=0,0','--autoplay-policy=no-user-gesture-required'],env:{...process.env,DISPLAY:display,PULSE_SINK:sink}});
  const c=await browser.newContext({viewport:null,acceptDownloads:true});await c.addCookies([{name:'koubo_session',value:privateState.owner,domain:new URL(base).hostname,path:'/'}]);
  await c.addInitScript(id=>localStorage.setItem('koubo.projectId',id),privateState.project.id);const p=await c.newPage();await p.goto(base+'/delivery');
  for(const video of await p.locator('video').all())await video.evaluate(v=>new Promise(r=>{v.addEventListener('seeked',r,{once:true});v.currentTime=1}));
  fd=fs.openSync(path.join(out,'recording_ffmpeg.log'),'w');
  recorder=spawn('ffmpeg',['-y','-hide_banner','-thread_queue_size','1024','-f','x11grab','-framerate','25','-video_size','1440x1000','-i',display+'.0','-thread_queue_size','1024','-f','pulse','-i',sink+'.monitor','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-movflags','+faststart',path.join(out,'walkthrough.mp4')],{stdio:['pipe','ignore',fd],env:{...process.env,DISPLAY:display}});
  done=new Promise((resolve,reject)=>{recorder.once('exit',code=>code===0?resolve():reject(new Error('FFmpeg '+code)));recorder.once('error',reject)});
  await delay(2000);await p.locator('video').first().evaluate(v=>v.play());await delay(12000);await p.locator('video').first().evaluate(v=>v.pause());
  await p.locator('video').nth(1).evaluate(v=>{v.currentTime=0;return v.play()});await delay(27000);
  await p.goto(base);await p.locator('[data-action="show-result"]').first().click();await p.locator('#result-video').waitFor();await delay(4000);
  await p.locator('[data-action="loop-cut"]').click();await delay(6000);await p.locator('[data-action="stop-cut"]').click();
  const d=p.waitForEvent('download');await p.locator('[data-download="mp4"]').click();await(await d).saveAs(path.join(root,'data/optimization_recording_download.mp4'));await delay(4000);
  recorder.stdin.write('q\n');await done;recorder=null;
  const file=path.join(out,'walkthrough.mp4');const info=JSON.parse(execFileSync('ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',file]));
  const video=info.streams.find(s=>s.codec_type==='video'),audio=info.streams.find(s=>s.codec_type==='audio');assert(audio&&Number(video.nb_read_frames)>1200&&Number(info.format.duration)>50);
  const volume=spawnSync('ffmpeg',['-hide_banner','-i',file,'-af','volumedetect','-vn','-sn','-f','null','-'],{encoding:'utf8'});
  const mean=Number(volume.stderr.match(/mean_volume: ([\d.-]+) dB/)?.[1]);assert(volume.status===0&&Number.isFinite(mean)&&mean>-50,'Recording audio must not be silent');
  fs.writeFileSync(path.join(out,'recording_validation.json'),JSON.stringify({method:'Continuous actual X11 screen and isolated browser audio; post-inference preview, cut loop and download. No montage or replacement narration.',durationSeconds:Number(info.format.duration),frames:Number(video.nb_read_frames),audioCodec:audio.codec_name,videoCodec:video.codec_name,meanVolumeDb:mean},null,2)+'\n');console.log('Recorded',info.format.duration,'seconds');
 }finally{if(recorder){recorder.stdin.write('q\n');await done.catch(()=>{})}if(browser)await browser.close();if(fd)fs.closeSync(fd);execFileSync('pactl',['unload-module',moduleId],{env:{...process.env,DISPLAY:''}});xvfb.kill('SIGTERM')}
})().catch(e=>{console.error(e);process.exitCode=1});
