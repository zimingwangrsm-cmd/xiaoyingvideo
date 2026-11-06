const { chromium }=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs');const path=require('node:path');
const out=path.resolve(__dirname,'../deliverables/v2/research');fs.mkdirSync(out,{recursive:true});
const sources=[
 ['capcut','https://www.capcut.com/resource/edit-video-with-text','Transcript-based editing'],
 ['descript','https://help.descript.com/getting-started/edit-like-a-doc','Edit like a doc'],
 ['premiere','https://helpx.adobe.com/premiere/desktop/edit-projects/edit-video-using-text-based-editing/overview-of-text-based-editing.html','Text-Based Editing'],
 ['vivavideo','https://quvideo.com/zh-Hant/products','VivaVideo'],
];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE,
  proxy:process.env.https_proxy?{server:process.env.https_proxy}:undefined});
 const records=[];
 try{for(const [id,url,keyword]of sources){
  const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});
  try{
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForTimeout(3000);
   const matches=page.getByText(keyword,{exact:false});
   if(id==='vivavideo') {
     const exact=page.getByText('VivaVideo',{exact:true});
     for(let i=0;i<await exact.count();i++){const box=await exact.nth(i).boundingBox();if(box&&box.y>300){await exact.nth(i).scrollIntoViewIfNeeded();await page.evaluate(()=>scrollBy(0,-120));break;}}
   } else if(await matches.count())await matches.last().scrollIntoViewIfNeeded().catch(()=>{});
   await page.screenshot({path:path.join(out,id+'.png')});
   if(id==='capcut') { const img=page.locator('img[alt*="Showing how"]').first(); if(await img.count()) await img.screenshot({path:path.join(out,'capcut-interface.png')}); }
   const imgs=await page.locator('img').evaluateAll(els=>els.filter(e=>e.naturalWidth>400&&e.naturalHeight>150).map(e=>({src:e.currentSrc,alt:e.alt,width:e.naturalWidth,height:e.naturalHeight})).slice(0,10));
   records.push({id,url:page.url(),requestedUrl:url,title:await page.title(),httpStatus:response.status(),capturedAt:new Date().toISOString(),screenshot:id+'.png',evidenceType:'Official public documentation/site rendered in Chrome; not a logged-in product trial',images:imgs});
   console.log(id,response.status(),imgs.length);
  }catch(e){records.push({id,url,error:e.message});console.log(id,e.message)}finally{await page.close()}
 }}finally{await browser.close();fs.writeFileSync(path.join(out,'sources.json'),JSON.stringify(records,null,2)+'\n')}
})();
