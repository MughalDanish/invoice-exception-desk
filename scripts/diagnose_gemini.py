"""Read-only live probes. Never print credentials, prompts, or model output."""

import inspect
import io
import json
import socket
import time
import uuid

import httpx
from app.core.config import Settings
from app.db.models import Invoice
from app.db.session import build_engine
from app.modules.extraction.adapters import parse_extraction
from app.modules.extraction.gemini import PROMPT, SYSTEM_INSTRUCTION
from app.modules.extraction.gemini_schema import GeminiInvoice
from app.modules.invoices.storage import resolve_private_file
from google import genai
from google.genai import types
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session

settings = Settings()


def emit(**data):
    print(json.dumps(data), flush=True)


def probe(label, operation):
    start = time.perf_counter()
    try:
        result = operation()
        emit(
            probe=label,
            success=True,
            seconds=round(time.perf_counter() - start, 3),
            result=result,
        )
    except Exception as exc:  # noqa: BLE001 - Never emit upstream messages or payloads.
        emit(
            probe=label,
            success=False,
            seconds=round(time.perf_counter() - start, 3),
            exception=type(exc).__name__,
            status=getattr(exc, "code", None),
        )


host = "generativelanguage.googleapis.com"
probe("DNS", lambda: {"resolved_addresses": len(socket.getaddrinfo(host, 443))})


def https():
    with httpx.Client(timeout=httpx.Timeout(15, connect=10)) as client:
        r = client.get("https://" + host)
        return {"status": r.status_code, "tls_reached": True}


probe("HTTPS", https)
emit(
    model=settings.gemini_model,
    configured_timeout_seconds=settings.gemini_timeout_seconds,
    diagnostic_timeout_seconds=60,
    sdk_attempts=1,
    application_attempts=1,
)
from google.genai import _api_client

source = inspect.getsource(_api_client)
lines = source.splitlines()
for i, line in enumerate(lines):
    if ("/ 1000" in line or "milliseconds" in line.lower()) and "timeout" in "\n".join(
        lines[max(0, i - 2) : i + 2]
    ).lower():
        emit(sdk_timeout_source=" | ".join(lines[max(0, i - 2) : i + 2]).strip())


def call(contents, config):
    with genai.Client(
        api_key=settings.gemini_api_key.get_secret_value(),
        http_options=types.HttpOptions(
            timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    ) as client:
        r = client.models.generate_content(
            model=settings.gemini_model, contents=contents, config=config
        )
        return r


probe(
    "1_text",
    lambda: {
        "has_output": bool(
            call(
                "Reply with OK.", types.GenerateContentConfig(max_output_tokens=32)
            ).text
        )
    },
)


def image():
    image = Image.new("RGB", (800, 220), "white")
    ImageDraw.Draw(image).text(
        (30, 60),
        "SYNTHETIC INVOICE: TEST-100  TOTAL USD 12.34",
        fill="black",
        font_size=28,
    )
    b = io.BytesIO()
    image.save(b, format="PNG")
    r = call(
        [
            types.Part.from_bytes(data=b.getvalue(), mime_type="image/png"),
            "Extract the invoice reference and total as plain text.",
        ],
        types.GenerateContentConfig(max_output_tokens=256),
    )
    return {"has_output": bool(r.text)}


probe("2_image_unstructured", image)


def invoice():
    engine = build_engine(settings.database_url)
    with Session(engine) as db:
        row = db.get(Invoice, uuid.UUID("abdb63bd-fb2c-4797-a233-6624c0d49726"))
        path = resolve_private_file(settings.storage_dir, row.file_path)
        data = path.read_bytes()
        mime = row.mime_type
    engine.dispose()
    r = call(
        [types.Part.from_bytes(data=data, mime_type=mime), PROMPT],
        types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION, response_mime_type="application/json",
            response_json_schema=GeminiInvoice.model_json_schema(),
            temperature=0,
            max_output_tokens=8192,
        ),
    )
    payload = json.loads(r.text or "")
    parse_extraction(payload)
    return {"schema_valid": True, "file_bytes": len(data)}


probe("3_actual_invoice_schema", invoice)
