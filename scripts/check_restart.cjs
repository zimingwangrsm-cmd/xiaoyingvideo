/* Run after stopping and restarting the acceptance server with the same DATA_DIR. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const base=process.env.APP_URL || 'http://127.0.0.1:8767';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
(async()=>{
 const saved=JSON.parse(fs.readFileSync(path.join(root,'data/browser_acceptance/project.json')));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try {
  const context=await browser.newContext({storageState:path.join(root,'data/browser_acceptance/storage.json')});
  const current=await context.request.get(base+'/api/projects/'+saved.id);
  assert.equal(current.status(),200);
  const p=await current.json();
  assert.equal(p.revision,saved.revision);assert.deepEqual(p.edit,saved.edit);
  const job=await context.request.get(base+'/api/jobs/'+p.latestRenderId).then(r=>r.json());
  assert.equal(job.status,'succeeded');assert.equal(job.isCurrent,false);
  assert.equal((await context.request.get(base+job.artifact.videoUrl)).status(),200);
  assert.equal((await context.request.get(base+job.artifact.downloadUrl)).status(),409);
  const page=await context.newPage();await page.goto(base);await page.locator('#source-video').waitFor();
  await page.locator('[data-action="show-result"]').click();await page.locator('#result-video').waitFor();
  await page.locator('video').evaluate(v=>v.play());
  await page.waitForFunction(()=>document.querySelector('video').currentTime>1);
  const result={testedAt:new Date().toISOString(),baseUrl:base,projectId:p.id,revision:p.revision,passed:['persisted cookie ownership','same revision and edit after real server restart','completed artifact retained','stale download remains rejected','browser restores project and plays persisted artifact']};
  fs.writeFileSync(path.join(root,'deliverables/restart_validation.json'),JSON.stringify(result,null,2)+'\n');
  console.log(result);
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
