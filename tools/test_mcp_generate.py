"""E2E test: MCP tools/call generate_model with a real sample image."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = str(ROOT / "mcp_server" / "meshforge_mcp.py")

samples = sorted((ROOT / "app" / "ui" / "samples").glob("*.png")) or \
          sorted((ROOT / "app" / "ui" / "samples").glob("*.jpg"))
if not samples:
    sys.exit("No sample images found")
img = str(samples[0])
print(f"[Test] Using image: {img}")

msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "generate_model",
                  "arguments": {"image_path": img, "resolution": 128}}}

proc = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        text=True, encoding="utf-8")
out, _ = proc.communicate(json.dumps(msg) + "\n", timeout=900)

resp = json.loads(out.strip().splitlines()[-1])
payload = json.loads(resp["result"]["content"][0]["text"])
print(json.dumps(payload, indent=2, ensure_ascii=False))

glb = payload.get("glb_path", "")
ok = payload.get("success") and glb and os.path.isfile(glb) and os.path.getsize(glb) > 1000
print("MCP_GENERATE_TEST:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)