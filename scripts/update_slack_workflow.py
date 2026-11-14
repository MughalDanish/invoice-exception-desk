"""Update a saved export while preserving intake configuration and credential references."""
import copy
import json
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]);target=Path(sys.argv[2])
w=json.loads(source.read_text(encoding="utf-8-sig"))
if isinstance(w,list):w=w[0]
w=copy.deepcopy(w)
nodes={n["name"]:n for n in w["nodes"]}
backend=nodes["Backend intake"]
if not backend.get("credentials",{}).get("httpHeaderAuth"):
    raise SystemExit("Select backend Header Auth credentials before updating the live workflow")
backend.setdefault("parameters",{}).setdefault("options",{})["timeout"]=240000
formatter=(root/"n8n/notifications/slack-notification.cjs").read_text(encoding="utf-8")
formatter=formatter[:formatter.index("module.exports =")]
nodes["Safe result"]["parameters"]["jsCode"] = formatter + '\nreturn $input.all().map(item => ({json: {...item.json, ...buildNotification(item.json, "http://localhost:3000")}}));'
condition=nodes["Needs review"]["parameters"]["conditions"]["conditions"][0]
condition["leftValue"]="={{ $json.notify ? 'SEND' : 'SKIP' }}"
condition["rightValue"]="SEND"
slack=next(n for n in w["nodes"] if n["type"]=="n8n-nodes-base.slack")
slack["parameters"]["messageType"]="block"
slack["parameters"]["blocksUi"]="={{ $json.slack_blocks }}"
slack["parameters"]["text"]="={{ $json.notification }}"
slack["parameters"].setdefault("otherOptions",{})["includeLinkToWorkflow"]=False
# Current node versions expose the newer attribution switch at the top level.
slack["parameters"]["appendAttribution"]=False
fetch={"id":"invoice-notification-details","name":"Fetch invoice details","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[875,-80],"parameters":{"method":"GET","url":"=http://backend:8000/api/v1/integrations/n8n/invoices/{{ $json.invoice_id }}","authentication":"genericCredentialType","genericAuthType":"httpHeaderAuth","options":{"timeout":20000}},"credentials":copy.deepcopy(backend["credentials"]),"retryOnFail":True,"maxTries":2,"waitBetweenTries":1000,"onError":"continueErrorOutput"}
w["nodes"]=[n for n in w["nodes"] if n["name"]!=fetch["name"]]+[fetch]
w["connections"]["Backend intake"]["main"][0]=[{"node":fetch["name"],"type":"main","index":0}]
w["connections"][fetch["name"]]={"main":[[{"node":"Safe result","type":"main","index":0}],[{"node":"Sanitized integration failure","type":"main","index":0}]]}
w.setdefault("settings",{})["executionTimeout"]=300
# Keep publication state, Gmail/webhook settings, idempotency and all credentials intact.
target.write_text(json.dumps([w],indent=2),encoding="utf-8")
print("Updated notification presentation and read-only detail fetch; preserved intake and credential references.")
