"""Regenerate the credential-free, importable n8n workflow artifact."""

import json
from pathlib import Path


def node(name, kind, version, position, parameters, **options):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "type": "n8n-nodes-base." + kind,
        "typeVersion": version,
        "position": position,
        "parameters": parameters,
        **options,
    }


guard = """const items = $input.all();
if (items.length !== 1) throw new Error('ONE_ATTACHMENT_REQUIRED');
const item = items[0];
const keys = Object.keys(item.binary || {});
if (keys.length !== 1) throw new Error('ONE_ATTACHMENT_REQUIRED');
const key = keys[0], file = item.binary[key];
const mime = file.mimeType;
if (!['application/pdf', 'image/jpeg', 'image/png'].includes(mime)) throw new Error('UNSUPPORTED_ATTACHMENT');
if (!/\\.(pdf|jpe?g|png)$/i.test(file.fileName || '')) throw new Error('UNSUPPORTED_ATTACHMENT');
const bytes = await this.helpers.getBinaryDataBuffer(0, key);
if (!bytes.length || bytes.length > 8388608) throw new Error('ATTACHMENT_SIZE_INVALID');
const messageId = item.json.id || item.json.headers?.['x-delivery-id'];
if (typeof messageId !== 'string' || !/^[A-Za-z0-9._:@/-]{1,230}$/.test(messageId)) throw new Error('DELIVERY_ID_REQUIRED');
return [{json: {deliveryKey: messageId + ':attachment-0'}, binary: {file}}];"""

workflow = {
    "id": "invoice-desk-intake",
    "name": "Invoice Desk - authenticated intake",
    "active": False,
    "nodes": [
        node(
            "Fixture webhook",
            "webhook",
            2,
            [0, 0],
            {
                "httpMethod": "POST",
                "path": "invoice-intake",
                "authentication": "headerAuth",
                "responseMode": "onReceived",
                "options": {},
            },
            webhookId="invoice-desk-fixture-intake",
        ),
        node(
            "Gmail AP-DEMO",
            "gmailTrigger",
            1.2,
            [0, 220],
            {
                "pollTimes": {"item": [{"mode": "everyMinute"}]},
                "simple": False,
                "filters": {"labelIds": ["REPLACE_WITH_AP_DEMO_LABEL_ID"]},
                "options": {"downloadAttachments": True},
            },
            disabled=True,
        ),
        node("Validate one attachment", "code", 2, [250, 0], {"jsCode": guard}),
        node(
            "Backend intake",
            "httpRequest",
            4.2,
            [500, 0],
            {
                "method": "POST",
                "url": "http://backend:8000/api/v1/integrations/n8n/invoices",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
                "sendHeaders": True,
                "headerParameters": {
                    "parameters": [
                        {"name": "Idempotency-Key", "value": "={{ $json.deliveryKey }}"}
                    ]
                },
                "sendBody": True,
                "contentType": "multipart-form-data",
                "bodyParameters": {
                    "parameters": [
                        {
                            "parameterType": "formBinaryData",
                            "name": "file",
                            "inputDataFieldName": "file",
                        }
                    ]
                },
                "options": {"timeout": 60000},
            },
            retryOnFail=True,
            maxTries=3,
            waitBetweenTries=2000,
            onError="continueErrorOutput",
        ),
        node(
            "Safe result",
            "code",
            2,
            [750, -80],
            {
                "jsCode": "const r = $json; return [{json: {invoice_id: r.invoice_id, status: r.status, duplicate: r.duplicate, blocker_codes: r.blocker_codes || [], error_code: r.error_code || null, notification: 'Invoice ' + r.invoice_id + ': ' + r.status + '. Checks: ' + (r.blocker_codes || []).join(', ')}}];"
            },
        ),
        node(
            "Needs review",
            "if",
            2,
            [1000, -80],
            {
                "conditions": {
                    "options": {
                        "caseSensitive": True,
                        "typeValidation": "strict",
                        "version": 2,
                    },
                    "conditions": [
                        {
                            "id": "needs-review",
                            "leftValue": "={{ $json.status }}",
                            "rightValue": "NEEDS_REVIEW",
                            "operator": {"type": "string", "operation": "equals"},
                        }
                    ],
                    "combinator": "and",
                },
                "options": {},
            },
        ),
        node(
            "Optional Telegram alert",
            "telegram",
            1.2,
            [1250, -160],
            {
                "chatId": "REPLACE_WITH_LOCAL_CHAT_ID",
                "text": "={{ $json.notification }}",
                "additionalFields": {"appendAttribution": False},
            },
            disabled=True,
        ),
        node(
            "Sanitized integration failure",
            "code",
            2,
            [750, 160],
            {
                "jsCode": "console.warn('INVOICE_INTEGRATION_FAILED: inspect backend health and credentials; retry the same delivery ID.'); throw new Error('INVOICE_INTEGRATION_FAILED');"
            },
        ),
    ],
    "connections": {
        "Fixture webhook": {
            "main": [[{"node": "Validate one attachment", "type": "main", "index": 0}]]
        },
        "Gmail AP-DEMO": {
            "main": [[{"node": "Validate one attachment", "type": "main", "index": 0}]]
        },
        "Validate one attachment": {
            "main": [[{"node": "Backend intake", "type": "main", "index": 0}]]
        },
        "Backend intake": {
            "main": [
                [{"node": "Safe result", "type": "main", "index": 0}],
                [{"node": "Sanitized integration failure", "type": "main", "index": 0}],
            ]
        },
        "Safe result": {
            "main": [[{"node": "Needs review", "type": "main", "index": 0}]]
        },
        "Needs review": {
            "main": [
                [{"node": "Optional Telegram alert", "type": "main", "index": 0}],
                [],
            ]
        },
    },
    "settings": {
        "executionOrder": "v1",
        "executionTimeout": 240,
        "saveDataErrorExecution": "none",
        "saveDataSuccessExecution": "none",
        "saveManualExecutions": False,
    },
    "pinData": {},
    "tags": [],
}

if __name__ == "__main__":
    path = Path(__file__).parent / "workflows/invoice-intake.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
