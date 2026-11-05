/* Real Chromium acceptance against the loopback app; no mocked responses. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const out = path.resolve(process.env.EVIDENCE_DIR || path.join(root, 'deliverables'));
fs.mkdirSync(out, { recursive: true });
const privateDir = path.join(root, 'data', 'browser_acceptance');
const base = process.env.APP_URL || 'http://127.0.0.1:8767';
assert(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
fs.mkdirSync(privateDir, { recursive: true });
const checks = [];
const errors = [];
function pass(name, details = {}) { checks.push({ name, ...details }); console.log('PASS', name); }
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  let project;
  async function action(selector) {
    const [response] = await Promise.all([
      page.waitForResponse(r => r.url().endsWith('/actions') && r.request().method() === 'POST'),
      page.locator(selector).first().click(),
    ]);
    assert.equal(response.status(), 200);
    project = await response.json();
    await page.waitForFunction(() => document.querySelector('.saved-label')?.textContent.includes('选择已保存'));
    return project;
  }
  async function screenshot(name) { await page.screenshot({ path: path.join(out, name + '.png'), fullPage: true }); }
  async function play(selector, seek = 1) {
    await page.locator(selector).evaluate((video, time) => { video.currentTime = time; return video.play(); }, seek);
    await page.waitForFunction(({selector, seek}) => { const v = document.querySelector(selector); return v && !v.paused && v.currentTime > seek + 1 && v.videoWidth > 0; }, { selector, seek });
    const info = await page.locator(selector).evaluate(v => ({ time: v.currentTime, duration: v.duration, width: v.videoWidth, height: v.videoHeight, decodedFrames: v.getVideoPlaybackQuality().totalVideoFrames, cues: v.textTracks[0]?.cues?.length, activeCues: v.textTracks[0]?.activeCues?.length, audioDecodedBytes: v.webkitAudioDecodedByteCount }));
    assert(info.cues > 0); assert(info.activeCues > 0); assert(info.decodedFrames > 0); assert(info.audioDecodedBytes > 0);
    await page.locator(selector).evaluate(v => v.pause());
    return info;
  }
  try {
    await page.goto(base);
    await page.locator('[data-action="start-sample"]').waitFor();
    await screenshot('browser_start');
    const created = page.waitForResponse(r => r.url().endsWith('/from-sample'));
    await page.locator('[data-action="start-sample"]').click();
    project = await (await created).json();
    await page.locator('#source-video').waitFor();
    assert.equal(await page.locator('.edit-block').count(), 13);
    pass('sample and explicit synthetic/rules labels', { projectId: project.id });
    const cookie = (await context.cookies()).find(c => c.name === 'koubo_session');
    assert(cookie.httpOnly && cookie.sameSite === 'Lax');
    const stranger = await browser.newContext();
    const denied = await stranger.request.get(base + '/api/projects/' + project.id);
    assert.equal(denied.status(), 404);
    await stranger.close();
    pass('browser cookie flags and separate-context isolation');
    pass('source H264/AAC playback and active VTT', await play('#source-video'));
    await page.locator('[data-action="seek"][data-id="s05"]').click();
    const start = project.blocks.find(b => b.id === 's05').clipStartFrame / 30;
    await page.waitForFunction(t => Math.abs(document.querySelector('video').currentTime - t) < .1, start);
    pass('text click seeks source', { seconds: start });
    for (const id of ['s03', 's04', 's05']) await action(`[data-action="lock"][data-id="${id}"]`);
    assert(await page.locator('[data-action="delete"][data-id="s03"]').isDisabled());
    await action('[data-action="set-preset"][data-seconds="30"]');
    assert.equal(project.metrics.targetStatus, 'locked_conflict');
    assert(await page.locator('[data-action="render"]').isDisabled());
    await screenshot('browser_conflict');
    pass('locked conflict and disabled delete/export', { lockedDurationMs: project.metrics.lockedDurationMs });
    await action('[data-action="set-preset"][data-seconds="90"]');
    const prior = structuredClone(project.edit);
    const proposalResponse = page.waitForResponse(r => r.url().endsWith('/proposals'));
    await page.locator('[data-action="propose"]').first().click();
    const proposal = await (await proposalResponse).json();
    await page.locator('[data-action="apply-proposal"]').waitFor();
    assert.equal((await context.request.get(base + '/api/projects/' + project.id).then(r => r.json())).revision, project.revision);
    await screenshot('browser_proposal');
    await action('[data-action="apply-proposal"]');
    assert(project.metrics.deletedCount > 0);
    for (const id of prior.lockedBlockIds) assert(project.edit.keptBlockIds.includes(id));
    pass('proposal needs explicit apply and preserves locks', { source: proposal.source, plannedDurationMs: project.metrics.plannedDurationMs });
    const afterProposal = structuredClone(project.edit);
    await action('[data-action="undo"]');
    assert.deepEqual(project.edit.keptBlockIds, prior.keptBlockIds);
    await page.locator('[data-action="propose"]').first().click();
    await page.locator('[data-action="apply-proposal"]').waitFor();
    await action('[data-action="apply-proposal"]');
    assert.deepEqual(project.edit.keptBlockIds, afterProposal.keptBlockIds);
    const deleted = project.blocks.find(b => !project.edit.keptBlockIds.includes(b.id)).id;
    await page.locator('#only-deleted').check();
    assert.equal(await page.locator('.edit-block').count(), project.metrics.deletedCount);
    await action(`[data-action="restore"][data-id="${deleted}"]`);
    await page.locator('#only-deleted').uncheck();
    await action('[data-action="undo"]');
    pass('undo proposal and filter/restore/undo');
    // Inject the application's documented development-only failure header, never a fake response.
    await page.route('**/proposals', route => route.continue({ headers: { ...route.request().headers(), 'X-Demo-Fail': 'proposal' } }));
    await page.locator('[data-action="propose"]').first().click();
    await page.locator('[data-action="retry-operation"]').waitFor();
    assert.deepEqual((await context.request.get(base + '/api/projects/' + project.id).then(r => r.json())).edit.keptBlockIds, project.edit.keptBlockIds);
    await page.unroute('**/proposals');
    await page.locator('[data-action="retry-operation"]').click();
    await page.locator('[data-action="apply-proposal"]').waitFor();
    pass('real proposal failure and retry preserve choices');
    await page.locator('[data-action="dismiss-proposal"]').click();
    const finalKeep = ['s01', 's03', 's04', 's05', 's07', 's10', 's12'];
    for (const b of project.blocks) {
      if (project.edit.keptBlockIds.includes(b.id) && !finalKeep.includes(b.id))
        await action(`[data-action="delete"][data-id="${b.id}"]`);
    }
    assert(project.metrics.plannedDurationMs <= 90000);
    pass('manual review brings conservative proposal within target', { plannedDurationMs: project.metrics.plannedDurationMs });
    await page.route('**/renders', route => route.continue({ headers: { ...route.request().headers(), 'X-Demo-Fail': 'render' } }));
    await page.locator('[data-action="render"]').click();
    await page.locator('.job-status.failed').waitFor({ timeout: 30000 });
    await screenshot('browser_failure');
    await page.unroute('**/renders');
    await page.locator('.job-status.failed [data-action="render"]').click();
    await page.locator('#result-video').waitFor({ timeout: 300000 });
    pass('real render failure and retry');
    pass('result H264/AAC playback and active VTT', await play('#result-video'));
    await screenshot('browser_result');
    const downloaded = {};
    for (const [kind, filename] of [['mp4', 'browser_download.mp4'], ['srt', 'browser_download.srt'], ['record', 'browser_download_record.json']]) {
      const event = page.waitForEvent('download');
      await page.locator(`[data-download="${kind}"]`).click();
      const download = await event;
      assert.equal(await download.failure(), null);
      await download.saveAs(path.join(out, filename));
      downloaded[kind] = filename;
    }
    const crypto = require('node:crypto');
    const sha = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(out, file))).digest('hex');
    const record = JSON.parse(fs.readFileSync(path.join(out, downloaded.record)));
    assert.equal(sha(downloaded.mp4), record.videoSha256);
    assert.equal(sha(downloaded.srt), record.subtitleSha256);
    pass('actual browser MP4/SRT/record downloads and SHA256', downloaded);
    await page.locator('[data-action="back-editor"]').click();
    const completedRevision = project.revision;
    await action('[data-action="set-preset"][data-seconds="90"]');
    assert.equal(project.revision, completedRevision);
    await page.locator('[data-action="show-result"]').first().click();
    await page.getByText('短片已准备好', { exact: true }).waitFor();
    assert.equal(await page.locator('[data-download]').count(), 3);
    pass('reselecting current target retains current artifact and downloads');
    await page.locator('[data-action="back-editor"]').click();
    const restoreId = project.blocks.find(b => !project.edit.keptBlockIds.includes(b.id)).id;
    await action(`[data-action="restore"][data-id="${restoreId}"]`);
    await page.locator('[data-action="show-result"]').click();
    await page.getByText('这是上一版短片', { exact: true }).waitFor();
    assert.equal(await page.locator('[data-download]').count(), 0);
    await screenshot('browser_stale');
    pass('edited result marked stale and downloads absent');
    await page.locator('[data-action="back-editor"]').click();
    await page.reload();
    await page.locator('#source-video').waitFor();
    assert(await page.locator(`[data-action="delete"][data-id="${restoreId}"]`).isVisible());
    pass('refresh restores project and choices');
    await play('#source-video');
    await screenshot('browser_editor');
    for (const [width, height] of [[1280,720],[390,844]]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(() => window.scrollTo(0, 0));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await screenshot(width === 390 ? 'browser_mobile' : 'browser_desktop');
    }
    pass('desktop/mobile no horizontal overflow');
    await page.setViewportSize({ width: 1440, height: 1000 });
    // Save private cookie/session state only under ignored data/, for real restart validation.
    await context.storageState({ path: path.join(privateDir, 'storage.json') });
    fs.writeFileSync(path.join(privateDir, 'project.json'), JSON.stringify(project));
    // Additional edge cases in a separate project, leaving the recorded project recoverable.
    await page.locator('[data-action="new-project"]').click();
    const nextCreated = page.waitForResponse(r => r.url().endsWith('/from-sample'));
    await page.locator('[data-action="start-sample"]').click();
    project = await (await nextCreated).json();
    await page.locator('#source-video').waitFor();
    for (const b of project.blocks) await action(`[data-action="delete"][data-id="${b.id}"]`);
    assert.equal(project.metrics.keptCount, 0);
    assert(await page.locator('[data-action="render"]').isDisabled());
    await action('[data-action="restore-all"]');
    assert.equal(project.metrics.keptCount, 13);
    for (const b of project.blocks.slice(0, 5)) await action(`[data-action="lock"][data-id="${b.id}"]`);
    assert(await page.locator('[data-action="lock"][data-id="s06"]').isDisabled());
    pass('empty selection, restore all, five-lock limit');
    const beforeImport = structuredClone(project);
    await page.locator('[data-action="new-project"]').click();
    const sample = path.join(root, 'fixtures/interview_intro_v1');
    await page.locator('input[name="video"]').setInputFiles(path.join(sample, 'canonical.mp4'));
    await page.locator('input[name="subtitles"]').setInputFiles({ name:'invalid.srt', mimeType:'text/plain', buffer:Buffer.from('invalid subtitle') });
    await page.locator('#import-form button[type="submit"]').click();
    await page.getByText('素材暂时无法使用', { exact: false }).waitFor({ timeout: 180000 });
    pass('actual malformed SRT upload rejected visibly');
    await screenshot('browser_invalid_upload');
    assert.equal(await page.evaluate(() => localStorage.getItem('koubo.projectId')), beforeImport.id);
    await page.locator('[data-action="previous-project"]').click();
    await page.locator('#source-video').waitFor();
    assert.equal(await page.locator('.edit-block.locked').count(), 5);
    const restoredPrevious = await context.request.get(base + '/api/projects/' + beforeImport.id).then(r => r.json());
    assert.deepEqual(restoredPrevious.edit, beforeImport.edit);
    await page.locator('[data-action="new-project"]').click();
    await page.locator('input[name="video"]').setInputFiles(path.join(sample, 'canonical.mp4'));
    await page.locator('input[name="subtitles"]').setInputFiles({name:'bad_utf8.srt',mimeType:'text/plain',buffer:Buffer.from([255,254,128])});
    await page.locator('#import-form button[type="submit"]').click();
    await page.getByText('素材暂时无法使用', {exact:true}).waitFor();
    await page.reload();
    await page.locator('#source-video').waitFor();
    assert.equal(await page.locator('.edit-block.locked').count(), 5);
    assert.equal(await page.evaluate(() => localStorage.getItem('koubo.projectId')), beforeImport.id);
    pass('failed replacement upload keeps prior edit and refresh recovery');
    await page.locator('[data-action="new-project"]').click();
    await page.locator('input[name="video"]').setInputFiles(path.join(sample, 'canonical.mp4'));
    await page.locator('input[name="subtitles"]').setInputFiles(path.join(sample, 'sample.srt'));
    await page.locator('#import-form button[type="submit"]').click();
    await page.locator('#source-video').waitFor({ timeout: 180000 });
    assert(await page.getByText('自己的素材', { exact: true }).isVisible());
    pass('real MP4/SRT multipart import becomes editable');
    assert.deepEqual(errors, []);
    pass('no uncaught browser JavaScript errors');
    fs.writeFileSync(path.join(out, 'browser_validation.json'), JSON.stringify({ testedAt: new Date().toISOString(), baseUrl: base, browser: await browser.version(), passed: checks, pageErrors: errors }, null, 2) + '\n');
  } catch (error) {
    await screenshot('browser_check_failure');
    fs.writeFileSync(path.join(out, 'browser_failure_report.json'), JSON.stringify({ checks, errors, failure: error.stack }, null, 2));
    throw error;
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
