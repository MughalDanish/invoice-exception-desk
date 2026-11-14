// Supplemental safe interactions: only GET APIs, unsaved browser drafts, no submit.
import { chromium } from '../../../frontend/node_modules/playwright/index.mjs';
import { readFileSync,writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('../../../',import.meta.url));
const env=Object.fromEntries(readFileSync(`${root}/.env`,'utf8').split(/\r?\n/).filter(l=>/^[A-Z_]+=/.test(l)).map(l=>{const i=l.indexOf('=');return[l.slice(0,i),l.slice(i+1).replace(/^(['"])(.*)\1$/,'$2')];}));
const browser=await chromium.launch();const report={consoleErrors:[],pageErrors:[],failedRequests:[],checks:[],screens:[]};
try{
 const context=await browser.newContext({viewport:{width:1440,height:900}});const page=await context.newPage();
 page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});page.on('pageerror',e=>report.pageErrors.push(e.message));page.on('requestfailed',r=>report.failedRequests.push({url:r.url(),failure:r.failure()?.errorText}));
 await context.route('**/api/v1/**',r=>['GET','HEAD','OPTIONS'].includes(r.request().method())?r.continue():r.abort());
 await page.goto('http://localhost:3000');await page.getByLabel('Username',{exact:true}).fill(env.DEMO_BASIC_USER);await page.getByLabel('Password',{exact:true}).fill(env.DEMO_BASIC_PASSWORD);await page.getByRole('button',{name:'Open workspace'}).click();await page.getByRole('region',{name:'Invoice statistics'}).waitFor();
 await page.getByRole('link',{name:'All invoices',exact:true}).first().click();const row=page.locator('tbody tr').filter({hasText:'INV-A-004'});await row.getByRole('link',{name:'Review'}).click();await page.getByRole('heading',{name:'Invoice fields',exact:true}).waitFor();
 const actions=async()=>page.locator('.action-row button').evaluateAll(bs=>bs.map(b=>({text:b.textContent,disabled:b.disabled,height:Math.round(b.getBoundingClientRect().height)})));
 report.checks.push({name:'Ready actions',actions:await actions()});
 await page.getByLabel('Total',{exact:true}).fill('1150.01');await page.getByLabel('Review / correction notes').fill('Unsaved browser-only audit draft; no action submitted.');report.checks.push({name:'Unsaved correction',actions:await actions()});
 for(const [size,width,height] of [['desktop',1440,900],['mobile',390,844]]){await page.setViewportSize({width,height});const file=`private-unsaved-draft-${size}.png`;await page.screenshot({path:`${root}/storage/ui-audit/${file}`,fullPage:true,mask:[page.locator('.operator')]});report.screens.push(file);}
 await page.getByRole('tab',{name:'Review invoice',exact:true}).focus();await page.keyboard.press('ArrowRight');report.checks.push({name:'ArrowRight from Review tab',focused:await page.evaluate(()=>document.activeElement.textContent),selected:await page.getByRole('tab',{selected:true}).innerText()});
 await page.getByRole('tab',{name:'Audit history'}).click();await page.getByRole('tab',{name:'Review invoice',exact:true}).click();report.checks.push({name:'Draft remains on tab switch',value:await page.getByLabel('Total',{exact:true}).inputValue()});
 // Navigate away without save, then inspect another local read-only mode.
 await page.getByRole('link',{name:'Overview',exact:true}).click();await page.getByRole('region',{name:'Invoice statistics'}).waitFor();
 await page.goto('http://localhost:3002');await page.getByRole('region',{name:'Invoice statistics'}).waitFor();await page.locator('nav a[href="/exceptions/"]').click();await page.getByLabel('Issue type').selectOption('TOTAL_MISMATCH');await page.locator('tbody tr').first().getByRole('link',{name:'Review'}).click();await page.getByRole('heading',{name:'Source document',exact:true}).waitFor();await page.getByRole('tab',{name:'Audit history'}).click();
 report.checks.push({name:'Public controls hidden',postButtons:await page.getByRole('button',{name:'Post to ledger'}).count()});
 console.log(JSON.stringify(report));
}finally{await browser.close();writeFileSync(`${root}/storage/ui-audit/probe.json`,JSON.stringify(report,null,2));}
