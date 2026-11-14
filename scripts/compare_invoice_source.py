"""Read-only source comparison. Print field names and match flags, never invoice values."""
import json
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import Settings
from app.db.models import Invoice, ValidationResult
from app.db.session import build_engine
from app.modules.invoices.storage import resolve_private_file

s=Settings();engine=build_engine(s.database_url)
with Session(engine) as db:
 row=db.get(Invoice,uuid.UUID("abdb63bd-fb2c-4797-a233-6624c0d49726"))
 path=resolve_private_file(s.storage_dir,row.file_path)
 data=row.extracted_data
 print(json.dumps({"invoice_status":row.status.value,"mime_type":row.mime_type,"has_extraction":bool(data)}),flush=True)
 if not data:raise SystemExit(0)
 if row.mime_type!="application/pdf":
  print(json.dumps({"comparison":"visual_review_required"}));raise SystemExit(0)
 text="\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
 folded=" ".join(text.casefold().split())
 print(json.dumps({"source_text_available":bool(text.strip()),"pages":len(PdfReader(path).pages)}),flush=True)
 def emit(field,match,method="source_text_presence"):
  print(json.dumps({"field":field,"match":match,"method":method}),flush=True)
 def present(value):return " ".join(str(value).casefold().split()) in folded
 for field in ["vendor_name","vendor_tax_id","invoice_number","currency"]:
  value=data.get(field)
  emit(field,present(value) if value is not None else None)
 for field in ["invoice_date","due_date"]:
  value=data.get(field)
  if value is None:emit(field,None);continue
  variants=[value]
  try:
   d=date.fromisoformat(value)
   variants += [d.strftime(f) for f in ["%d/%m/%Y","%m/%d/%Y","%d-%m-%Y","%d %B %Y","%B %d, %Y","%d %b %Y"]]
  except ValueError:pass
  emit(field,any(present(v) for v in variants),"date_text_representation")
 token=re.compile(r"(?<![\w.])[+-]?[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?%?(?![\w.])")
 def numbers(source):
  result=[]
  for value in token.findall(source):
   try:
    if value.endswith("%"):
     d=Decimal(value[:-1].replace(",",""));sign,digits,exp=d.as_tuple();result.append(Decimal((sign,digits,exp-2)))
    else:result.append(Decimal(value.replace(",","")))
   except InvalidOperation:pass
  return result
 labels={"subtotal":r"\bsub\s*total\b","tax_amount":r"\b(?:tax|vat|gst)\b","total":r"\b(?:total|amount due|balance due)\b"}
 lines=text.splitlines()
 for field in ["subtotal","tax_rate","tax_amount","total"]:
  value=data.get(field)
  if value is None:emit(field,None);continue
  if field=="tax_rate":
   values=numbers(" ".join(v for v in token.findall(text) if v.endswith("%")))
   emit(field,Decimal(value) in values,"explicit_percentage_in_source")
  else:
   relevant=[]
   for i,line in enumerate(lines):
    if re.search(labels[field],line,re.I) and not (field=="total" and re.search(r"sub\s*total",line,re.I)):
     relevant += numbers(" ".join(lines[i:i+2]))
   emit(field,Decimal(value) in relevant,"label_adjacent_numeric_match")
 all_numbers=numbers(text)
 for i,item in enumerate(data.get("line_items",[])):
  desc=item.get("description")
  emit(f"line_items.{i}.description",present(desc) if desc is not None else None)
  for field in ["quantity","unit_price","line_total"]:
   value=item.get(field)
   emit(f"line_items.{i}.{field}",Decimal(value) in all_numbers if value is not None else None,"numeric_presence_only")
 failures=db.scalars(select(ValidationResult).where(ValidationResult.invoice_id==row.id,ValidationResult.passed.is_(False))).all()
 print(json.dumps({"failed_validation_codes":sorted({r.rule_code for r in failures})}),flush=True)
engine.dispose()
