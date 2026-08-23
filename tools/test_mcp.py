"""Smoke-test for mcp_server/meshforge_mcp.py: initialize + tools/list + get_status."""
import json
import subprocess
import sys
from pathlib import Path

SERVER = str(Path(__file__).resolve().parent.parent / "mcp_server" / "meshforge_mcp.py")

msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "get_status", "arguments": {}}},
]

proc = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        text=True, encoding="utf-8")
stdin_data = "\n".join(json.dumps(m) for m in msgs) + "\n"
out, _ = proc.communicate(stdin_data, timeout=180)

ok = True
for line in out.strip().splitlines():
    resp = json.loads(line)
    rid = resp.get("id")
    if rid == 1:
        name = resp["result"]["serverInfo"]["name"]
        print(f"initialize -> serverInfo={name} protocol={resp['result']['protocolVersion']}")
        ok &= name == "meshforge3d"
    elif rid == 2:
        tools = [t["name"] for t in resp["result"]["tools"]]
        print(f"tools/list -> {tools}")
        ok &= set(tools) == {"get_status", "generate_model", "text_to_3d"}
    elif rid == 3:
        payload = json.loads(resp["result"]["content"][0]["text"])
        print(f"get_status -> {payload}")
        ok &= "license_tier" in payload

print("MCP_SMOKE_TEST:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)