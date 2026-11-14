// Pure presentation adapter. It never approves, posts, or repairs invoice amounts.
function buildNotification(invoice, dashboardBaseUrl) {
  const templates = {
    NEEDS_REVIEW: { title: "\u26a0\ufe0f Invoice requires review", status: "Requires review", next: "Open the invoice, compare the exceptions with the original document, and resolve verified issues. Revalidate before requesting approval." },
    EXTRACTION_FAILED: { title: "\u274c Invoice extraction failed", status: "Extraction failed", next: "Open the original document and check that it is readable. Retry extraction when the issue is resolved; never fill missing fields by guessing." },
    READY_TO_POST: { title: "\u2705 Invoice ready to post", status: "Ready to post", next: "Open the invoice and confirm the current version has the required human approval before posting. This notification does not approve or post it." },
  };
  const template = templates[invoice.status];
  if (!template) return { notify: false };
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(invoice.invoice_id || "")) throw new Error("INVALID_NOTIFICATION_INVOICE_ID");
  // n8n Code runs without browser URL globals. Accept an explicit root HTTP(S) origin.
  if (typeof dashboardBaseUrl !== "string" || !/^https?:\/\/(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?|\[[0-9a-f:]+\])(?::[0-9]{1,5})?\/?$/i.test(dashboardBaseUrl)) throw new Error("INVALID_REVIEW_BASE_URL");
  const reviewUrl = dashboardBaseUrl.replace(/\/$/, "") + "/invoices/detail/?id=" + invoice.invoice_id;
  const missing = invoice.status === "EXTRACTION_FAILED" ? "Not extracted" : "Not provided";
  const text = (value, limit=300) => typeof value === "string" && value.trim() ? [...value].slice(0,limit).join("") : missing;
  const decimal = value => {
    if (typeof value !== "string" || !/^[+-]?[0-9]+(?:\.[0-9]+)?$/.test(value)) return missing;
    const [whole, fraction] = value.split(".");
    return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (fraction === undefined ? "" : "."+fraction);
  };
  const amount = decimal(invoice.total);
  const currency = typeof invoice.currency === "string" && invoice.currency.trim() ? invoice.currency : "Currency not provided";
  const sources = { gmail:"Gmail", upload:"Dashboard upload", manual:"Manual intake", webhook:"Webhook" };
  // Slack mrkdwn has its own escaping rules: never allow document text to become
  // a mention or explicit link. verbatim also disables automatic link/mention parsing.
  const escape = value => String(value).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/[\r\n\t]+/g," ");
  const md = value => escape(text(value));
  const dateText = value => {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return text(value);
    const parsed = new Date(value+"T00:00:00Z");
    if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0,10) !== value) return value;
    const [year,month,day] = value.split("-");
    const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const monthName=months[parseInt(month,10)-1];
    return monthName ? parseInt(day,10)+" "+monthName+" "+year : value;
  };
  const money = value => decimal(value) === missing ? missing : decimal(value)+" "+currency;
  const exceptions = {
    MISSING_REQUIRED_FIELD:"Required invoice information is missing.", INVALID_DATE:"An invoice date is invalid or unreadable.",
    INVALID_DATE_RANGE:"The due date is earlier than the invoice date.", NEGATIVE_AMOUNT:"A financial amount is negative.",
    INVALID_TAX_RATE:"The tax rate is outside the supported range.", ARITHMETIC_INCOMPLETE:"There is not enough information to verify the arithmetic.",
    LINE_TOTAL_MISMATCH:"A line total does not match its quantity and unit price.", SUBTOTAL_MISMATCH:"The subtotal does not match the printed line totals.",
    TOTAL_MISMATCH:"The total does not match subtotal plus tax.", TAX_RATE_MISMATCH:"The printed tax amount does not match the stated rate.",
    UNAPPROVED_VENDOR:"The supplier is not approved in the supplier registry.", DUPLICATE_INVOICE:"This supplier and invoice number match an existing invoice.",
    DUPLICATE_FILE:"This document has already been received.", CURRENCY_MISMATCH:"The currency differs from the supplier policy.",
    AMOUNT_OUTLIER:"The amount exceeds the supplier review threshold.", UNSUPPORTED_CURRENCY:"The currency is not supported for posting.",
    UNCERTAIN_EXTRACTION:"Some extracted fields are uncertain and need comparison with the source.",
  };
  const failures = (Array.isArray(invoice.validations) ? invoice.validations : []).filter(r=>r.passed===false)
    .sort((a,b)=>(a.severity==="BLOCKER"?0:1)-(b.severity==="BLOCKER"?0:1));
  const reasons = [...new Set(failures.map(r=>exceptions[r.rule_code] || "A validation check requires review in the application."))];
  const errors = {
    GEMINI_TIMEOUT:"The extraction service did not respond in time.", GEMINI_API_ERROR:"The extraction service could not complete the request.",
    INVALID_EXTRACTION_OUTPUT:"The extraction response did not meet the required financial data format.",
    GEMINI_EMPTY_RESPONSE:"The extraction service returned no usable text.", GEMINI_RESPONSE_TRUNCATED:"The extraction response was incomplete.",
    GEMINI_MALFORMED_JSON:"The extraction response could not be read safely.", GEMINI_RESPONSE_BLOCKED:"The document could not be processed by the extraction service.",
  };
  const totalCheck = failures.find(r => r.rule_code === "TOTAL_MISMATCH");
  // Differences are supplied by backend validation; never calculate or repair totals here.
  const difference = totalCheck && typeof totalCheck.difference_amount === "string"
    ? decimal(totalCheck.difference_amount) : missing;
  const signedDifference = difference === missing ? null
    : (/^-/.test(difference) ? difference : "+"+difference) + " " + currency;
  const limit=3;
  const exceptionLines=failures.slice(0,limit).map(r => {
    const icon=r.severity === "BLOCKER" ? "\u{1f534}" : "\u{1f7e0}";
    let label=exceptions[r.rule_code] || "A validation check needs review.";
    if(r.rule_code === "TOTAL_MISMATCH") {
      label="Total mismatch";
      if(decimal(r.expected_amount)!==missing) label += " \u2014 expected *"+escape(money(r.expected_amount))+"*";
    }
    if(r.rule_code === "UNAPPROVED_VENDOR") label="Supplier not approved";
    return icon+" "+label;
  });
  const more=failures.length>limit ? "\n_"+(failures.length-limit)+" more checks in the invoice._" : "";
  let action;
  if(invoice.status === "EXTRACTION_FAILED") action="Check the document, then retry extraction.";
  else if(invoice.status === "READY_TO_POST") action="Review the current version and confirm approval before posting.";
  else if(failures.some(r=>r.rule_code==="DUPLICATE_INVOICE")) action="Check the existing invoice before taking further action.";
  else if(failures.some(r=>r.rule_code==="UNAPPROVED_VENDOR") && totalCheck) action="Verify supplier approval and reconcile against the source.";
  else if(totalCheck) action="Compare the total with the source before correcting any fields.";
  else if(failures.some(r=>r.rule_code==="UNAPPROVED_VENDOR")) action="Verify supplier approval, then revalidate.";
  else action="Verify flagged details against the source, then revalidate.";
  const source=sources[invoice.source] || "Other intake source";
  const contextStatus={NEEDS_REVIEW:"Pending finance review",EXTRACTION_FAILED:"Awaiting extraction retry",READY_TO_POST:"Pending posting review"}[invoice.status];
  const markdown = value => ({type:"mrkdwn",text:value,verbatim:true});
  const identity="*"+md(invoice.invoice_number)+"* \u00b7 "+md(invoice.supplier_name);
  const financial="*Amount:* *"+escape(money(invoice.total))+"*"+(signedDifference?" \u00b7 *Difference:* "+escape(signedDifference):"");
  const dates="*Issued:* "+escape(dateText(invoice.invoice_date))+" \u00b7 *Due:* "+escape(dateText(invoice.due_date));
  let details;
  if(invoice.status === "EXTRACTION_FAILED") details="*Extraction issue*\n"+(errors[invoice.error_code] || "The document could not be extracted. Open the invoice for details.");
  else if(failures.length) details="*Exceptions ("+failures.length+")*\n"+exceptionLines.join("\n")+more;
  else details=invoice.status==="READY_TO_POST" ? "No blocking validation exceptions reported." : "Review the current validation results.";
  const blocks = [
    {type:"header",text:{type:"plain_text",text:template.title,emoji:true}},
    {type:"section",text:markdown(identity+"\n"+financial+"\n"+dates)},
    {type:"divider"},
    {type:"section",text:markdown(details+"\n*Action:* "+action)},
    {type:"actions",elements:[{type:"button",style:"primary",text:{type:"plain_text",text:"Review invoice",emoji:true},url:reviewUrl,action_id:"review_invoice"}]},
    {type:"context",elements:[markdown("Source: "+source+" \u00b7 "+contextStatus)]},
  ];
  const notification=template.title+" - "+text(invoice.invoice_number)+" | "+text(invoice.supplier_name)+" | "+money(invoice.total)+"\n"+action;
  return {notify:true,notification,slack_blocks:JSON.stringify({blocks}),review_url:reviewUrl};
}
module.exports = { buildNotification };
