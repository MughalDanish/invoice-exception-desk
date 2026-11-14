const { test } = require("node:test");
const assert = require("node:assert/strict");
const { buildNotification } = require("./slack-notification.cjs");
const id = "12345678-1234-1234-1234-123456789abc";
const base = { invoice_id:id, status:"NEEDS_REVIEW", invoice_number:"DEMO-2042", supplier_name:"Example Supplier", invoice_date:"2026-11-14", due_date:"2026-12-14", total:"9999999999999999.990000", currency:"USD", source:"gmail", validations:[{rule_code:"TOTAL_MISMATCH", severity:"BLOCKER", passed:false,expected_amount:"9999999999999699.990000",difference_amount:"300.000000"},{rule_code:"UNAPPROVED_VENDOR",severity:"BLOCKER",passed:false}] };
const format = value => buildNotification(value,"http://localhost:3000");
const blocks = value => JSON.parse(format(value).slack_blocks).blocks;

test("mobile layout has compact markdown, one divider, context and primary link",()=>{
 const b=blocks(base);assert.equal(b.length,6);assert.equal(b[0].text.type,"plain_text");
 assert.equal(b.filter(v=>v.type==="divider").length,1);
 for(const section of b.filter(v=>v.type==="section")){assert.equal(section.text.type,"mrkdwn");assert.equal(section.text.verbatim,true);assert.equal(section.fields,undefined);assert.ok(section.text.text.length<=3000);}
 assert.match(b[1].text.text,/\*Amount:\*/);assert.match(b[1].text.text,/14 Nov 2026/);assert.match(b[1].text.text,/9,999,999,999,999,999\.990000 USD/);
 assert.match(b[3].text.text,/\*Exceptions \(2\)\*/);assert.match(b[3].text.text,/\*Action:\*/);
 const action=b.find(v=>v.type==="actions").elements[0];assert.equal(action.style,"primary");assert.equal(action.url,`http://localhost:3000/invoices/detail/?id=${id}`);
 assert.equal(b.at(-1).type,"context");assert.equal(b.at(-1).elements[0].type,"mrkdwn");
});
test("discrepancy comes only from supplied validation evidence",()=>{
 assert.match(blocks(base)[1].text.text,/\+300\.000000 USD/);assert.match(blocks(base)[3].text.text,/expected \*9,999,999,999,999,699\.990000 USD\*/);
 const noEvidence={...base,validations:[{rule_code:"TOTAL_MISMATCH",passed:false}]};assert.doesNotMatch(JSON.stringify(blocks(noEvidence)),/Difference:|expected \*/);
});
test("distinct failure and ready templates preserve unknowns and approval boundaries",()=>{
 const failure=blocks({invoice_id:id,status:"EXTRACTION_FAILED",error_code:"GEMINI_TIMEOUT"});assert.match(failure[0].text.text,/extraction failed/);assert.match(failure[1].text.text,/Not extracted/);assert.match(failure[3].text.text,/did not respond in time/);assert.doesNotMatch(JSON.stringify(failure),/0\.00|Example Supplier/);
 const ready=blocks({...base,status:"READY_TO_POST",validations:[]});assert.match(ready[0].text.text,/ready to post/);assert.match(ready[3].text.text,/confirm approval before posting/);
});
test("document text cannot inject Slack mentions or explicit links",()=>{
 const b=blocks({...base,supplier_name:"<!channel> <https://evil.test|click> & vendor"});assert.match(b[1].text.text,/&lt;!channel&gt;/);assert.match(b[1].text.text,/&amp; vendor/);assert.doesNotMatch(b[1].text.text,/<!channel>|<https:/);
});
test("bounded exceptions and absent currency never fabricate financial information",()=>{
 const b=blocks({...base,total:null,currency:null,validations:Array.from({length:8},()=>({rule_code:"PRIVATE_RULE",passed:false}))});assert.doesNotMatch(JSON.stringify(b),/PRIVATE_RULE|USD|0\.00/);assert.match(b[3].text.text,/5 more checks/);assert.match(b[1].text.text,/Not provided/);
 for(const status of ["EXTRACTING","RECEIVED","POSTED","REJECTED","UNKNOWN"])assert.equal(format({...base,status}).notify,false);
});
test("sandbox has no URL or module globals",()=>{
 const vm=require("node:vm"),fs=require("node:fs");let code=fs.readFileSync(require.resolve("./slack-notification.cjs"),"utf8");code=code.slice(0,code.indexOf("module.exports ="));const result=vm.runInNewContext(code+";buildNotification(invoice, dashboardBaseUrl)",{invoice:base,dashboardBaseUrl:"http://localhost:3000"});assert.equal(result.review_url,`http://localhost:3000/invoices/detail/?id=${id}`);
 for(const origin of ["javascript:alert(1)","https://user:password@example.com","https://example.com/path","https://example.com?x=1"])assert.throws(()=>buildNotification(base,origin),/INVALID_REVIEW_BASE_URL/);
});
