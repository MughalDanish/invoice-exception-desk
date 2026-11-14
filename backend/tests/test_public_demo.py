import asyncio
import copy
import json
import uuid

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.config import Settings
from app.core.middleware import PublicReadOnly
from app.modules import public_demo
from tests.conftest import AUTH, operator_auth


@pytest.fixture
def public_client(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Public mode attempted database access")

    monkeypatch.setattr(main, "build_engine", forbidden)
    settings = Settings(
        _env_file=None,
        public_demo=True,
        storage_dir=tmp_path,
        demo_basic_user=AUTH[0],
        demo_basic_password=AUTH[1],
        n8n_integration_key="test-integration-key",
    )
    with TestClient(main.create_app(settings)) as client:
        assert client.app.state.engine is None
        yield client


@pytest.mark.parametrize("auth", ["anonymous", "operator", "integration"])
@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/v1/invoices/upload"),
        ("POST", "/api/v1/integrations/n8n/invoices"),
        ("POST", "/api/v1/vendors"),
        ("PATCH", "/api/v1/invoices/{id}"),
        ("POST", "/api/v1/invoices/{id}/process"),
        ("POST", "/api/v1/invoices/{id}/revalidate"),
        ("POST", "/api/v1/invoices/{id}/review"),
        ("POST", "/api/v1/invoices/{id}/post"),
        ("DELETE", "/api/v1/invoices/{id}"),
        ("POST", "/api/v1/invoices/{id}/investigations"),
        ("PUT", "/unknown-future-route"),
    ],
)
def test_public_mutations_fail_closed(public_client, auth, method, path):
    kwargs = {"content": b"untrusted body"}
    if auth == "operator":
        kwargs["auth"] = AUTH
    if auth == "integration":
        kwargs["headers"] = {"X-Integration-Key": "test-integration-key"}
    response = public_client.request(method, path.format(id=uuid.uuid4()), **kwargs)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PUBLIC_DEMO_READ_ONLY"


def test_public_synthetic_reads_and_bundled_files(public_client, tmp_path):
    (tmp_path / "private.pdf").write_bytes(b"private document must never be served")
    assert public_client.get("/health").json()["database"] == "not_used"
    assert public_client.get("/api/v1/config").json()["read_only"] is True
    all_rows = public_client.get("/api/v1/invoices?limit=100").json()
    assert all_rows["total"] == 15
    review = public_client.get("/api/v1/invoices?status=NEEDS_REVIEW&issue=TOTAL_MISMATCH").json()
    assert review["total"] >= 1
    row = review["items"][0]
    record = public_client.get(f"/api/v1/invoices/{row['id']}").json()
    assert record["current_data"]["total"] == "2500.00"
    assert "file_path" not in record
    source = public_client.get(f"/api/v1/invoices/{row['id']}/file")
    assert source.status_code == 200
    assert source.content == (public_demo.BUNDLED / "invoices" / row["filename"]).read_bytes()
    assert public_client.get(f"/api/v1/invoices/{row['id']}/audit").status_code == 200
    assert public_client.get("/api/v1/invoices?page=2&limit=1").json()["page"] == 2
    assert public_client.get("/api/v1/invoices?search=%25").json()["total"] == 0
    assert public_client.get("/api/v1/ledger").json()["total"] == 1
    assert public_client.get("/api/v1/vendors").status_code == 200
    assert public_client.get("/api/v1/stats").json()["total_invoices"] == 15
    for path in (
        "/docs",
        "/openapi.json",
        "/api/v1/ledger/export.csv",
        f"/api/v1/invoices/{uuid.uuid4()}/file",
    ):
        assert public_client.get(path).status_code == 404


def test_public_restart_and_credentials_cannot_change_read_model(public_client):
    before = public_client.get("/api/v1/invoices?limit=100").json()
    data = copy.deepcopy(before)
    for item in data["items"]:
        public_client.patch(
            f"/api/v1/invoices/{item['id']}",
            **operator_auth(public_client),
            json={"expected_revision": 1, "changes": {"total": "0"}},
        )
    assert public_client.get("/api/v1/invoices?limit=100").json() == before
    with TestClient(main.create_app(Settings(_env_file=None, public_demo=True))) as restarted:
        assert restarted.get("/api/v1/invoices?limit=100").json() == before
    assert (
        public_client.options(
            "/api/v1/stats",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        ).status_code
        == 400
    )


def test_public_refuses_live_provider():
    with pytest.raises(ValueError):
        Settings(_env_file=None, public_demo=True, ai_mode="gemini")


def test_readonly_guard_never_consumes_body():
    async def check():
        messages = []

        async def forbidden(*args):
            raise AssertionError("Public write reached body parser or downstream route")

        async def send(message):
            messages.append(message)

        await PublicReadOnly(forbidden)({"type": "http", "method": "POST"}, forbidden, send)
        assert messages[0]["status"] == 403

    asyncio.run(check())


def test_public_rejects_changed_payload(monkeypatch, tmp_path):
    data = public_demo.load_public_data()
    data["invoices"][0]["current_data"]["total"] = "1.00"
    (tmp_path / "public-demo.json").write_text(json.dumps(data))
    (tmp_path / "answers.json").write_bytes((public_demo.BUNDLED / "answers.json").read_bytes())
    monkeypatch.setattr(public_demo, "BUNDLED", tmp_path)
    with pytest.raises(ValueError, match="synthetic answer key"):
        public_demo.load_public_data()
