"""Read-only schema probe; output contains metadata and safe error categories only."""
import json
import time
import re
import uuid
from google import genai
from google.genai import types
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.db.models import Invoice
from app.db.session import build_engine
from app.modules.extraction.gemini import PROMPT, SYSTEM_INSTRUCTION
from app.modules.extraction.gemini_schema import GeminiInvoice
from app.modules.extraction.schemas import InvoiceExtraction
from app.modules.invoices.storage import resolve_private_file
s=Settings();engine=build_engine(s.database_url)
with Session(engine) as db:
 row=db.get(Invoice,uuid.UUID("abdb63bd-fb2c-4797-a233-6624c0d49726"))
 content=resolve_private_file(s.storage_dir,row.file_path).read_bytes();mime=row.mime_type
engine.dispose()
allowed=set(InvoiceExtraction.model_fields)|{"description","quantity","unit_price","line_total"}
def safe_errors(exc):
 return [{"path":[str(v) if isinstance(v,int) or v in allowed else "<unknown-field>" for v in e["loc"]],"type":e["type"]} for e in exc.errors(include_input=False,include_context=False,include_url=False)][:30]
start=time.monotonic()
try:
 with genai.Client(api_key=s.gemini_api_key.get_secret_value(),http_options=types.HttpOptions(timeout=60000,retry_options=types.HttpRetryOptions(attempts=1))) as client:
  r=client.models.generate_content(model=s.gemini_model,contents=[types.Part.from_bytes(data=content,mime_type=mime),PROMPT],config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, response_mime_type="application/json",response_json_schema=GeminiInvoice.model_json_schema(),temperature=0,max_output_tokens=8192))
 print(json.dumps({"seconds":round(time.monotonic()-start,3),"finish_reasons":[getattr(c.finish_reason,"name","UNKNOWN") for c in r.candidates or []],"candidate_count":len(r.candidates or []),"text_chars":len(r.text or ""),"output_tokens":getattr(r.usage_metadata,"candidates_token_count",None),"thought_tokens":getattr(r.usage_metadata,"thoughts_token_count",None)}),flush=True)
 try:payload=json.loads(r.text or "")
 except (ValueError,TypeError):print(json.dumps({"json_valid":False}),flush=True);raise SystemExit(0)
 for label,model in [("provider",GeminiInvoice),("domain",InvoiceExtraction)]:
  try:model.model_validate(payload);print(json.dumps({"schema":label,"valid":True}),flush=True)
  except ValidationError as exc:print(json.dumps({"schema":label,"valid":False,"errors":safe_errors(exc)}),flush=True)
 if isinstance(payload,dict):
  money=[]
  for key in ["subtotal","tax_rate","tax_amount","total"]:
   money.append((key,payload.get(key)))
  for i,item in enumerate(payload.get("line_items",[])):
   for key in ["quantity","unit_price","line_total"]:
    money.append((f"line_items.{i}.{key}",item.get(key)))
  for key,value in money:
   if isinstance(value,str):
    print(json.dumps({"field":key,"comma":"," in value,"percent":"%" in value,"currency_symbol":any(c in value for c in "$???"),"empty":not value.strip(),"canonical_decimal":bool(re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?",value)),"grouped_decimal":bool(re.fullmatch(r"[+-]?[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?",value)),"percent_decimal":bool(re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?%",value))}),flush=True)
 if isinstance(payload,dict):
  print(json.dumps({"field_types":{k:type(v).__name__ for k,v in payload.items() if k in allowed}}),flush=True)
except Exception as exc:print(json.dumps({"exception":type(exc).__name__,"status":getattr(exc,"code",None)}),flush=True)
