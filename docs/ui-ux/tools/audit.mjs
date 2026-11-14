// Read-only local UI inspection. No HAR, trace, request headers or credentials saved.
import { chromium } from '../../../frontend/node_modules/playwright/index.mjs';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../../../', import.meta.url));
const out = path.join(root, 'storage/ui-audit'); mkdirSync(out, { recursive: true });
const env = Object.fromEntries(readFileSync(path.join(root, '.env'), 'utf8').split(/\r?\n/).filter(l => /^[A-Z_]+=/.test(l)).map(l => { const i=l.indexOf('='); return [l.slice(0,i),l.slice(i+1).replace(/^(['"])(.*)\1$/, '$2')]; }));
const sizes = { desktop:[1440,900], laptop:[1280,800], tablet:[768,1024], mobile:[390,844] };
const browser = await chromium.launch(); const result = { capturedAt:new Date().toISOString(), screens:[], modes:[], blockedWrites:[], checks:[] };
try {
 for (const [mode, port, api] of [['private',3000,8000],['public',3002,8002]]) {
  const context = await browser.newContext({ viewport:{width:1440,height:900} });
  const page = await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await context.route('**/api/v1/**',async route=>{ if (!['GET','HEAD','OPTIONS'].includes(route.request().method())) { result.blockedWrites.push({mode,method:route.request().method()}); return route.abort(); } await route.continue(); });
  const token = mode==='private' ? Buffer.from(`${env.DEMO_BASIC_USER}:${env.DEMO_BASIC_PASSWORD}`).toString('base64') : '';
  const get = async suffix => { const r=await context.request.get(`http://localhost:${api}/api/v1${suffix}`,{headers:token?{Authorization:`Basic ${token}`}:{}}); if(!r.ok())throw Error(`Read failed ${r.status()}`);return r.json(); };
  const before={stats:await get('/stats'),ledger:await get('/ledger'),vendors:await get('/vendors')};
  result.modes.push({mode,url:`http://localhost:${port}`,total:before.stats.total_invoices,statuses:before.stats.by_status});
  async function capture(name) {
   for(const [size,[width,height]] of Object.entries(sizes)) {
    await page.setViewportSize({width,height}); await page.waitForTimeout(120);
    const metrics = await page.evaluate(()=>{
     const box=e=>{ const s=getComputedStyle(e),r=e.getBoundingClientRect();return {tag:e.tagName,text:(e.textContent||'').trim().slice(0,90),font:s.fontSize,weight:s.fontWeight,color:s.color,background:s.backgroundColor,width:Math.round(r.width),height:Math.round(r.height)};};
     return {width:innerWidth,scroll:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,headings:[...document.querySelectorAll('h1,h2')].map(box),samples:[...document.querySelectorAll('th,td,.muted,.kpi small,.rule p,.badge,.pager button,.sidebar nav a')].filter(e=>e.getClientRects().length).slice(0,24).map(box),tabs:[...document.querySelectorAll('[role=tab]')].map(e=>({selected:e.getAttribute('aria-selected'),controls:e.getAttribute('aria-controls'),tabindex:e.getAttribute('tabindex')})),mainCount:document.querySelectorAll('main').length,navCurrent:document.querySelectorAll('nav [aria-current]').length,skipLinks:document.querySelectorAll('a[href="#main"],a[href="#main-content"]').length,inputs:[...document.querySelectorAll('input')].map(e=>({name:e.getAttribute('aria-label')||e.name,type:e.type,disabled:e.disabled})),buttons:[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length).map(e=>({text:e.textContent.trim(),disabled:e.disabled,width:Math.round(e.getBoundingClientRect().width),height:Math.round(e.getBoundingClientRect().height)})),rawBlocks:document.querySelectorAll('pre').length,scrollTables:[...document.querySelectorAll('.table-scroll')].map(e=>({client:e.clientWidth,scroll:e.scrollWidth}))};
    });
    const filename=`${mode}-${name}-${size}.png`;
    // Operator identity and any login field are masked even though screenshots are ignored.
    await page.screenshot({path:path.join(out,filename),fullPage:true,mask:[page.locator('.operator'),page.locator('input[name=username]'),page.locator('input[name=password]')]});
    result.screens.push({mode,name,size,file:filename,...metrics});
   }
   await page.setViewportSize({width:1440,height:900});
  }
  await page.goto(`http://localhost:${port}`);
  if(mode==='private') {
   await page.getByLabel('Username',{exact:true}).waitFor();await capture('login');
   await page.getByLabel('Username',{exact:true}).fill(env.DEMO_BASIC_USER);
   await page.getByLabel('Password',{exact:true}).fill(env.DEMO_BASIC_PASSWORD);
   await page.getByRole('button',{name:'Open workspace'}).click();
  }
  await page.getByRole('region',{name:'Invoice statistics'}).waitFor();await page.locator('tbody tr').first().waitFor();await capture('overview');
  for(const [href,name] of [['/invoices/','invoices'],['/exceptions/','exceptions'],['/ledger/','ledger'],['/vendors/','suppliers']]) {
   await page.locator(`nav a[href="${href}"]`).click(); await page.waitForTimeout(400); await capture(name);
   if(mode==='private'&&name==='invoices') {await page.getByRole('button',{name:'Upload invoice'}).click();await capture('upload');await page.getByRole('button',{name:'Cancel',exact:true}).click();}
   if(mode==='private'&&name==='suppliers') {await page.getByRole('button',{name:'Register supplier'}).click();await capture('supplier-form');await page.getByRole('button',{name:'Cancel',exact:true}).click();}
   if(mode==='private'&&name==='ledger') {const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV'}).click();const file=await download;await file.saveAs(path.join(out,'private-ledger.csv'));result.checks.push({mode,name:'CSV download',filename:file.suggestedFilename(),failure:await file.failure()});}
  }
  await page.locator('nav a[href="/invoices/"]').click();await page.getByLabel('Search invoices').fill('no-results-ui-audit');await page.getByRole('heading',{name:'No invoices here'}).waitFor();await capture('empty-search');
  await page.getByLabel('Search invoices').fill('');await page.locator('tbody tr').first().waitFor();
  const items=(await get('/invoices?limit=100')).items;
  const chosen=[...new Map(items.map(i=>[i.status,i])).values()];
  const corrected=items.find(i=>i.revision>1);if(corrected&&!chosen.some(c=>c.id===corrected.id))chosen.push(corrected);
  // Include corrected posted invoice and duplicate / arithmetic public cases.
  for(const code of ['TOTAL_MISMATCH','DUPLICATE_INVOICE']){const item=items.find(i=>i.issue_codes.includes(code));if(item&&!chosen.some(c=>c.id===item.id))chosen.push(item);}
  for(const item of chosen){
   await page.locator(`a[href="/invoices/detail/?id=${item.id}"]`).first().count().then(async n=>{if(n)await page.locator(`a[href="/invoices/detail/?id=${item.id}"]`).first().click();else{await page.locator('nav a[href="/invoices/"]').click();await page.locator(`a[href="/invoices/detail/?id=${item.id}"]`).first().click();}});
   await page.getByRole('heading',{name:'Source document',exact:true}).waitFor(); await page.waitForTimeout(200);
   const detail=await get(`/invoices/${item.id}`); const name=`detail-${item.filename.replace(/\.pdf$/,'')}-${item.status.toLowerCase()}`;
   await capture(name);
   result.checks.push({mode,name,revision:detail.revision,originalTotal:detail.extracted_data?.total,currentTotal:detail.current_data?.total,rules:detail.validations.map(r=>({code:r.rule_code,passed:r.passed,severity:r.severity})),reviewCount:detail.reviews.length});
   await page.locator('.raw-extraction summary').click();await capture(`${name}-original`);
   await page.getByRole('tab',{name:'Audit history'}).click();await capture(`${name}-audit`);
   await page.locator('nav a[href="/invoices/"]').click();await page.locator('tbody tr').first().waitFor();
  }
  // Controlled request interception only; these are not live API failures.
  await context.route('**/api/v1/invoices?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'AUDIT_SIMULATED_FAILURE',message:'Simulated service unavailable for UI audit'}})}));
  await page.locator('nav a[href="/exceptions/"]').click();await page.locator('.notice.error').waitFor();await capture('simulated-error');
  await context.unroute('**/api/v1/invoices?**');
  await context.route('**/api/v1/invoices?**',async route=>{await new Promise(r=>setTimeout(r,1800));await route.continue();});
  await page.locator('nav a[href="/invoices/"]').click();await page.getByText('Loading invoices…',{exact:true}).waitFor();await capture('simulated-loading');
  await context.unroute('**/api/v1/invoices?**');await page.waitForTimeout(1900);
  const after={stats:await get('/stats'),ledger:await get('/ledger'),vendors:await get('/vendors')};
  result.checks.push({mode,name:'No data mutations',unchanged:JSON.stringify(before)===JSON.stringify(after),pageErrors:errors});
  await context.close();
 }
} finally {await browser.close();writeFileSync(path.join(out,'evidence.json'),JSON.stringify(result,null,2));}
console.log(JSON.stringify({screens:result.screens.length,modes:result.modes,checks:result.checks.filter(c=>c.name==='No data mutations'),blockedWrites:result.blockedWrites.length}));
