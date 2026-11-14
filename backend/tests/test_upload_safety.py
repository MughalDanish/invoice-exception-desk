import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader

from app.core.config import Settings
from app.core.errors import AppError
from app.modules.invoices.storage import resolve_private_file, validate_file
from tests.conftest import AUTH, ROOT, operator_auth


def test_all_synthetic_pdfs_match_answer_key():
    import hashlib

    answers = json.loads((ROOT / "fixtures" / "answers.json").read_text())
    assert len(answers["fixtures"]) == 16
    for filename, expected in answers["fixtures"].items():
        content = (ROOT / "fixtures" / "invoices" / filename).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected["sha256"]
        assert "SYNTHETIC INVOICE" in PdfReader(io.BytesIO(content)).pages[0].extract_text()
        assert (
            validate_file(filename, "application/pdf", content, 8388608).sha256
            == expected["sha256"]
        )


@pytest.mark.parametrize(
    "filename,mime,body,status,code",
    [
        ("empty.pdf", "application/pdf", b"", 400, "EMPTY_FILE"),
        ("invoice.exe", "application/octet-stream", b"MZ", 415, "UNSUPPORTED_FILE_TYPE"),
        ("invoice.pdf", "image/png", b"%PDF-1.4", 415, "MIME_MISMATCH"),
        ("invoice.pdf", "application/pdf", b"not a pdf", 415, "INVALID_SIGNATURE"),
        ("invoice.pdf", "application/pdf", b"%PDF-1.4\ntruncated", 400, "MALFORMED_FILE"),
        ("invoice.png", "image/png", b"\x89PNG\r\n\x1a\ntruncated", 400, "MALFORMED_FILE"),
        ("invoice.jpg", "image/jpeg", b"\xff\xd8\xfftruncated", 400, "MALFORMED_FILE"),
    ],
)
def test_bad_uploads_rejected_without_database(
    authenticated_client, filename, mime, body, status, code
):
    response = authenticated_client.post(
        "/api/v1/invoices/upload",
        files={"file": (filename, body, mime)},
        **operator_auth(authenticated_client),
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize(
    "format,mime,filename",
    [
        ("PNG", "image/png", "invoice.png"),
        ("JPEG", "image/jpeg", "invoice.jpeg"),
    ],
)
def test_genuine_images_accepted(format, mime, filename):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format=format)
    assert validate_file(filename, mime, buffer.getvalue(), 8388608).mime_type == mime


def test_extension_case_and_path_sanitization(clean_pdf):
    file = validate_file("../../secret\\invoice.PDF", "application/pdf", clean_pdf, 8388608)
    assert file.filename == "invoice.pdf"


def test_file_limit_enforced(clean_pdf):
    with pytest.raises(AppError) as exc:
        validate_file("invoice.pdf", "application/pdf", clean_pdf, len(clean_pdf) - 1)
    assert exc.value.status == 413


def test_multipart_size_cap(client):
    result = client.post(
        "/api/v1/invoices/upload", **operator_auth(client), content=b"x" * (8388608 + 65537)
    )
    assert result.status_code == 413
    assert result.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_size_limit_for_chunked_requests(client):
    def chunks():
        for _ in range(130):
            yield b"x" * 65536

    result = client.post(
        "/api/v1/invoices/upload",
        **operator_auth(client),
        content=chunks(),
        headers={"Content-Type": "multipart/form-data; boundary=limit"},
    )
    assert result.status_code == 413


def test_storage_cannot_escape_root(tmp_path):
    private = tmp_path / "uploads"
    private.mkdir()
    (tmp_path / "outside.pdf").write_bytes(b"private")
    with pytest.raises(AppError, match="Original file is unavailable"):
        resolve_private_file(private, "../outside.pdf")


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/invoices",
        "/api/v1/vendors",
        "/docs",
        "/openapi.json",
        "/api/v1/invoices/00000000-0000-0000-0000-000000000001/file",
    ],
)
def test_sensitive_routes_require_auth(client, path):
    result = client.get(path)
    assert result.status_code == 401
    assert "www-authenticate" not in result.headers


def test_upload_requires_auth(client, clean_pdf):
    result = client.post(
        "/api/v1/invoices/upload", files={"file": ("a.pdf", clean_pdf, "application/pdf")}
    )
    assert result.status_code == 401


def test_wrong_password_rejected(client):
    assert client.get("/api/v1/invoices", auth=(AUTH[0], "wrong")).status_code == 401


def test_authenticated_openapi(authenticated_client):
    result = authenticated_client.get("/openapi.json")
    assert result.status_code == 200
    assert "/api/v1/invoices/upload" in result.json()["paths"]


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_cors_only_allows_local_frontend(client, origin):
    good = client.options(
        "/api/v1/invoices",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-csrf-token",
        },
    )
    bad = client.options(
        "/api/v1/invoices",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert good.status_code == 200
    assert good.headers["access-control-allow-origin"] == origin
    assert bad.status_code == 400
    assert "access-control-allow-origin" not in bad.headers


@pytest.mark.parametrize("password", ["", "CHANGE_ME"])
def test_no_default_authentication(password):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, auth_jwt_secret=password)
