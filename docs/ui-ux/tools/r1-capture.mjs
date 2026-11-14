// Read-only before/after captures of the same existing synthetic records.
import { chromium } from '../../../frontend/node_modules/playwright/index.mjs';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('../../../',import.meta.url));
const stage=process.argv[2];if(!['before','after'].includes(stage))throw Error('Use before or after');
const out=`${root}/storage/ui-r1/${stage}`;mkdirSync(out,{recursive:true});
const env=Object.fromEntries(readFileSync(`${root}/.env`,'utf8').split(/\r?\n/).filter(l=>/^[A-Z_]+=/.test(l)).map(l=>{const i=l.indexOf('=');return[l.slice(0,i),l.slice(i+1).replace(/^(['"])(.*)\1$/,'$2')];}));
const result={stage,at:new Date().toISOString(),screens:[],errors:[],unchanged:[]};const browser=await chromium.launch();
try{for(const [mode,port,api] of [['private',3000,8000],['public',3002,8002]]){
 const ctx=await browser.newContext({viewport:{width:1440,height:900}});const page=await ctx.newPage();page.on('pageerror',e=>result.errors.push(e.message));
 await ctx.route('**/api/v1/**',r=>['GET','HEAD','OPTIONS'].includes(r.request().method())?r.continue():r.abort());
 const token=mode==='private'?Buffer.from(`${env.DEMO_BASIC_USER}:${env.DEMO_BASIC_PASSWORD}`).toString('base64'):'';
 const get=async suffix=>(await ctx.request.get(`http://localhost:${api}/api/v1${suffix}`,{headers:token?{Authorization:`Basic ${token}`}:{}})).json();
 const rows=await get('/invoices?limit=100');const invoice=rows.items.find(i=>i.filename==='wrong-total.pdf');const before=await get(`/invoices/${invoice.id}`);const history=await get(`/invoices/${invoice.id}/audit`);
 await page.goto(`http://localhost:${port}`);if(mode==='private'){await page.getByLabel('Username',{exact:true}).fill(env.DEMO_BASIC_USER);await page.getByLabel('Password',{exact:true}).fill(env.DEMO_BASIC_PASSWORD);await page.getByRole('button',{name:'Open workspace'}).click();}
 await page.getByRole('region',{name:'Invoice statistics'}).waitFor();await page.locator('nav a[href="/invoices/"]').click();await page.locator(`a[href="/invoices/detail/?id=${invoice.id}"]`).click();await page.getByRole('heading',{name:'Source document',exact:true}).waitFor();
 async function shot(view){for(const [size,width,height] of [['desktop',1440,900],['laptop',1280,800],['tablet',768,1024],['mobile',390,844]]){await page.setViewportSize({width,height});const geometry=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight}));const file=`${mode}-${view}-${size}.png`;await page.screenshot({path:`${out}/${file}`,fullPage:true,mask:[page.locator('.operator')]});result.screens.push({file,...geometry});}await page.setViewportSize({width:1440,height:900});}
 await shot('review');
 if(stage==='before')await page.locator('.raw-extraction summary').click();else await page.getByRole('heading',{name:'Original extraction',exact:true}).scrollIntoViewIfNeeded();await shot('original');
 await page.getByRole('tab',{name:'Audit history'}).click();await shot('audit');
 if(stage==='after'){const correction=page.locator('article.event-content').filter({has:page.getByRole('heading',{name:'Invoice corrected',exact:true})});await (await correction.count()?correction.locator('.technical-details summary'):page.locator('.financial-timeline .technical-details summary').first()).click();await shot('technical');}
 result.unchanged.push({mode,detail:JSON.stringify(before)===JSON.stringify(await get(`/invoices/${invoice.id}`)),audit:JSON.stringify(history)===JSON.stringify(await get(`/invoices/${invoice.id}/audit`))});await ctx.close();
}}finally{await browser.close();writeFileSync(`${out}/evidence.json`,JSON.stringify(result,null,2));}
console.log(JSON.stringify({stage,screens:result.screens.length,overflows:result.screens.filter(s=>s.scroll>s.width),errors:result.errors,unchanged:result.unchanged}));
