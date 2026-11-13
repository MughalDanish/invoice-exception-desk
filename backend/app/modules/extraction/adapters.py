import hashlib
import json
from pathlib import Path
from typing import Protocol

from fastapi import Request
from pydantic import ValidationError

from app.modules.extraction.schemas import InvoiceExtraction


class ExtractionError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class Extractor(Protocol):
    def extract(self, file_path: Path, mime_type: str) -> InvoiceExtraction: ...


def parse_extraction(payload) -> InvoiceExtraction:
    try:
        data = InvoiceExtraction.model_validate(payload)
    except ValidationError as exc:
        raise ExtractionError("INVALID_EXTRACTION_OUTPUT") from exc
    if not any((data.vendor_name, data.invoice_number, data.total is not None)):
        raise ExtractionError("UNUSABLE_EXTRACTION")
    return data


class MockExtractor:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir

    def extract(self, file_path: Path, mime_type: str) -> InvoiceExtraction:
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        try:
            manifest = json.loads((self.fixtures_dir / "answers.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ExtractionError("MOCK_MANIFEST_UNAVAILABLE") from exc
        for fixture in manifest["fixtures"].values():
            if fixture["sha256"] == digest:
                if fixture["error_code"]:
                    raise ExtractionError(fixture["error_code"])
                return parse_extraction(fixture["extraction"])
        raise ExtractionError("MOCK_FIXTURE_NOT_FOUND")


def get_extractor(request: Request) -> Extractor:
    settings = request.app.state.settings
    if settings.ai_mode == "mock":
        return MockExtractor(settings.fixtures_dir)
    from app.modules.extraction.gemini import GeminiExtractor

    return GeminiExtractor(settings)
