// Synthetic Builder examples only; production notifications always use backend data.
const fs=require("node:fs"),path=require("node:path");
const {buildNotification}=require("../n8n/notifications/slack-notification.cjs");
const target=path.resolve(__dirname,"../storage/slack-block-kit");fs.mkdirSync(target,{recursive:true});
const sample={invoice_id:"12345678-1234-1234-1234-123456789abc",invoice_number:"DEMO-2042",supplier_name:"Example Software Solutions",invoice_date:"2026-11-14",due_date:"2026-12-14",total:"5800.00",currency:"USD",source:"gmail",status:"NEEDS_REVIEW",validations:[{rule_code:"TOTAL_MISMATCH",severity:"BLOCKER",passed:false,expected_amount:"5500.00",observed_amount:"5800.00",difference_amount:"300.00"},{rule_code:"UNAPPROVED_VENDOR",severity:"BLOCKER",passed:false}]};
for(const [name,input] of [["requires-review",sample],["extraction-failed",{invoice_id:sample.invoice_id,status:"EXTRACTION_FAILED",source:"gmail",error_code:"GEMINI_TIMEOUT"}],["ready-to-post",{...sample,status:"READY_TO_POST",validations:[]}]]){
 const result=buildNotification(input,"http://localhost:3000");const payload=JSON.parse(result.slack_blocks);
 fs.writeFileSync(path.join(target,name+".json"),JSON.stringify(payload,null,2));
 const link="https://app.slack.com/block-kit-builder/#"+encodeURIComponent(JSON.stringify(payload));
 fs.writeFileSync(path.join(target,name+"-builder.url"),"[InternetShortcut]\nURL="+link+"\n");
 console.log("Prepared synthetic Builder payload:",name);
}
