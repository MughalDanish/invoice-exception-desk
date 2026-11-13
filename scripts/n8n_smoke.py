"""Exercise exported intake nodes in real n8n using a synthetic PDF. No posting."""

import base64
import json
import re
import subprocess
import uuid
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, stdin=None):
    result = subprocess.run(
        ["docker", "compose", *args],
        check=False,
        cwd=ROOT,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=360,
        encoding="utf-8",
    )
    if result.returncode:
        path = ROOT / "storage/n8n-smoke-error.log"
        path.parent.mkdir(exist_ok=True)
        path.write_text(result.stdout + result.stderr, encoding="utf-8")
        raise SystemExit(
            "n8n command failed; inspect ignored storage/n8n-smoke-error.log locally."
        )
    return result.stdout


def main():
    key = dotenv_values(ROOT / ".env").get("N8N_INTEGRATION_KEY")
    if not key or key == "CHANGE_ME":
        raise SystemExit("Configure N8N_INTEGRATION_KEY in .env first")
    credential = [
        {
            "id": "invoice-desk-backend",
            "name": "Invoice Desk backend key",
            "type": "httpHeaderAuth",
            "data": {"name": "X-Integration-Key", "value": key},
        }
    ]
    docker(
        "exec",
        "-T",
        "n8n",
        "n8n",
        "import:credentials",
        "--input=/dev/stdin",
        stdin=json.dumps(credential),
    )
    original = json.loads((ROOT / "n8n/workflows/invoice-intake.json").read_text())
    workflow = {
        **original,
        "id": "invoice-desk-cli-smoke",
        "name": "Invoice Desk CLI smoke",
    }
    triggers = ("Fixture webhook", "Gmail AP-DEMO")
    workflow["nodes"] = [n for n in original["nodes"] if n["name"] not in triggers]
    workflow["connections"] = {
        k: v for k, v in original["connections"].items() if k not in triggers
    }
    data = base64.b64encode(
        (ROOT / "fixtures/invoices/clean-004.pdf").read_bytes()
    ).decode()
    workflow["nodes"][:0] = [
        {
            "id": "manual-smoke",
            "name": "Manual smoke",
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "position": [-500, 0],
            "parameters": {},
        },
        {
            "id": "fixture-smoke",
            "name": "Synthetic fixture",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [-250, 0],
            "parameters": {
                "jsCode": "return [{json:{id:'smoke-"
                + uuid.uuid4().hex
                + "'},binary:{file:{data:'"
                + data
                + "',mimeType:'application/pdf',fileName:'clean-004.pdf'}}}];"
            },
        },
    ]
    workflow["connections"]["Manual smoke"] = {
        "main": [[{"node": "Synthetic fixture", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Synthetic fixture"] = {
        "main": [[{"node": "Validate one attachment", "type": "main", "index": 0}]]
    }
    for node in workflow["nodes"]:
        if node["name"] == "Backend intake":
            node["credentials"] = {
                "httpHeaderAuth": {
                    "id": "invoice-desk-backend",
                    "name": "Invoice Desk backend key",
                }
            }
    # No secrets in the test workflow. Credentials and JSON are imported over stdin.
    docker(
        "exec",
        "-T",
        "n8n",
        "n8n",
        "import:workflow",
        "--input=/dev/stdin",
        stdin=json.dumps(workflow),
    )
    ids = []
    for _ in range(2):
        output = docker(
            "exec",
            "-T",
            "-e",
            "N8N_RUNNERS_BROKER_PORT=5680",
            "n8n",
            "n8n",
            "execute",
            "--id=invoice-desk-cli-smoke",
            "--rawOutput",
        )
        if '"invoice_id"' not in output or not any(
            state in output for state in ("READY_TO_POST", "NEEDS_REVIEW", "POSTED")
        ):
            (ROOT / "storage").mkdir(exist_ok=True)
            (ROOT / "storage/n8n-smoke-error.log").write_text(output, encoding="utf-8")
            raise SystemExit(
                "No backend result found; inspect ignored storage/n8n-smoke-error.log locally."
            )
        ids.append(set(re.findall(r'"invoice_id":\s*"([a-f0-9-]{36})"', output)))
    if not ids[0] or ids[0] != ids[1]:
        raise SystemExit("Replay did not return the same invoice identity")
    print(
        "PASS: real n8n intake validated a synthetic PDF twice and received the same backend invoice ID. No posting performed."
    )


if __name__ == "__main__":
    main()
