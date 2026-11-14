import { chromium } from '../../../frontend/node_modules/playwright/index.mjs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../../../',import.meta.url));
const out=path.join(root,'storage/ui-audit/concepts');mkdirSync(out,{recursive:true});
const browser=await chromium.launch();const evidence={screens:[],checks:[],errors:[],requests:[]};
try{
 const page=await browser.newPage();page.on('pageerror',e=>evidence.errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))evidence.requests.push(r.url());});
 for(const theme of ['a','b','c']){
  for(const view of ['overview','invoices','detail','exceptions','activity','original','future']){
   await page.goto(pathToFileURL(path.join(root,`docs/ui-ux/design-preview/theme-${theme}.html`)).href+`#${view}`);
   await page.locator('#content > *').first().waitFor();
   for(const [size,width,height] of [['desktop',1440,900],['laptop',1280,800],['tablet',768,1024],['mobile',390,844]]){
    await page.setViewportSize({width,height});
    const metrics=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,heading:document.querySelector('h1').textContent}));
    assert.ok(metrics.scroll<=width,`${theme}/${view}/${size}: page overflow`);
    const file=`${theme}-${view}-${size}.png`;await page.screenshot({path:path.join(out,file),fullPage:true});evidence.screens.push({theme,view,size,file,...metrics});
   }
   if(view==='invoices'){
    await page.locator('#invoice-search').fill('no-matches');assert.equal(await page.locator('tbody tr').count(),0);assert.ok(await page.locator('#empty-results').isVisible());await page.locator('#invoice-search').fill('Beta');assert.ok(await page.locator('tbody tr').count()>0);evidence.checks.push(`${theme}: search and empty state`);
   }
   if(view==='original'){
    const summary=page.locator('summary',{hasText:'View source JSON'});assert.equal(await page.locator('details[open]').count(),0);await summary.click();const text=await page.locator('pre').innerText();const source=JSON.parse(readFileSync(path.join(root,'fixtures/public-demo.json'),'utf8')).invoices.find(i=>i.filename==='wrong-total.pdf').extracted_data;assert.deepEqual(JSON.parse(text),source);await page.getByRole('button',{name:'Select JSON text',exact:true}).click();assert.ok((await page.evaluate(()=>getSelection().toString())).includes('2500.00'));evidence.checks.push(`${theme}: collapsed exact payload, syntax spans and manual-copy selection`);assert.ok(await page.locator('pre .string').count()>0);
   }
   if(view==='detail'){assert.equal(await page.locator('.action-bar button:not(:disabled)').count(),0);evidence.checks.push(`${theme}: financial actions disabled`);}
  }
 }
 assert.deepEqual(evidence.errors,[]);assert.deepEqual(evidence.requests,[]);
 console.log(JSON.stringify({screens:evidence.screens.length,checks:evidence.checks.length,pageErrors:evidence.errors,externalRequests:evidence.requests}));
}finally{await browser.close();writeFileSync(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2));}
