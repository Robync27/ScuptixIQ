"""
MeshForge 3D - VirusTotal preparation tool
===========================================
VirusTotal has a 650 MB per-file upload limit, so a 3.5 GB offline installer
cannot be uploaded directly. This tool solves it:

  1. Scans dist/MeshForge3D (or any folder) and computes SHA-256 for every file.
  2. Splits files into "uploadable" (<650 MB) and "too large" lists.
  3. Generates vt_report_hashes.csv + vt_report.txt for manual submission.
  4. Optionally auto-uploads files via the VT API v3 (--api-key).

Usage:
    python tools/vt_check.py                          # report only
    python tools/vt_check.py --api-key VT_KEY         # auto-upload small files
"""

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

VT_LIMIT = 650 * 1024 * 1024          # 650 MB hard upload limit
VT_API = "https://www.virustotal.com/api/v3"
NL = chr(13) + chr(10)                # CRLF


def sha256_of(path, buf_size=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(buf_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def collect_files(root):
    entries = []
    total = 0
    for p in sorted(root.rglob("*")):
        if p.is_file():
            size = p.stat().st_size
            total += size
            entries.append({"path": p, "size": size})
    return entries, total


def upload_to_vt(path, api_key):
    """Multipart upload of one file to VirusTotal API v3."""
    boundary = "----MeshForgeBoundary7MA4YWxkTrZu0gW"
    url = VT_API + "/files"

    with open(path, "rb") as f:
        data = f.read()

    head = (
        "--" + boundary + NL +
        'Content-Disposition: form-data; name="file"; filename="' +
        os.path.basename(path) + '"' + NL +
        "Content-Type: application/octet-stream" + NL + NL
    ).encode()
    tail = (NL + "--" + boundary + "--" + NL).encode()

    req = urllib.request.Request(
        url,
        data=head + data + tail,
        headers={
            "x-apikey": api_key,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode()[:300]}


def main():
    ap = argparse.ArgumentParser(description="Prepare files for VirusTotal scanning")
    ap.add_argument("--path", default=str(Path(__file__).resolve().parent.parent / "dist" / "MeshForge3D"),
                    help="Folder or single file to analyze")
    ap.add_argument("--api-key", default=os.environ.get("VT_API_KEY", ""),
                    help="VirusTotal API key (optional)")
    ap.add_argument("--out", default="vt_report", help="Output prefix")
    args = ap.parse_args()

    target = Path(args.path)
    if target.is_file():
        entries = [{"path": target, "size": target.stat().st_size}]
    else:
        entries, _total = collect_files(target)

    print("[VT] Analyzing %d files..." % len(entries))

    rows = []
    for e in entries:
        digest = sha256_of(e["path"])
        rel = str(e["path"].relative_to(target.parent)) if not target.is_file() else e["path"].name
        ok = e["size"] <= VT_LIMIT
        rows.append({
            "file": rel,
            "size_mb": round(e["size"] / (1024 * 1024), 2),
            "sha256": digest,
            "uploadable": "yes" if ok else "no (>650MB)",
        })

    csv_path = Path(args.out + "_hashes.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "size_mb", "sha256", "uploadable"])
        w.writeheader()
        w.writerows(rows)
    print("[VT] Hashes written to %s" % csv_path)

    lines = []
    lines.append("MeshForge 3D - VirusTotal submission plan")
    lines.append("=" * 60)
    lines.append("")
    lines.append("PRIORITY UPLOADS (executables and native modules):")
    for r in rows:
        if r["file"].endswith(".exe") or r["file"].endswith(".pyd"):
            lines.append("  %s  (%s MB)" % (r["file"], r["size_mb"]))
            lines.append("  SHA-256: %s" % r["sha256"])
    lines.append("")
    lines.append("ALL FILES:")
    for r in rows:
        lines.append("  [%10s] %s  %s" % (r["uploadable"], r["file"], r["sha256"]))
    txt_path = Path(args.out + ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(chr(10).join(lines))
    print("[VT] Report written to %s" % txt_path)

    if args.api_key:
        uploadable = [r for r in rows if r["uploadable"] == "yes"]
        print("[VT] Auto-uploading %d files via API..." % len(uploadable))
        for i, r in enumerate(uploadable, 1):
            p = target.parent / r["file"] if not target.is_file() else target
            print("  [%d/%d] %s ..." % (i, len(uploadable), r["file"]), end=" ", flush=True)
            res = upload_to_vt(p, args.api_key)
            if "error" in res:
                print("FAILED:", res["error"])
            else:
                aid = res.get("data", {}).get("id", "?")
                print("queued (analysis id: %s)" % aid)
            time.sleep(15)  # respect public API rate limits
        print("[VT] Done. Check results at virustotal.com by SHA-256.")
    else:
        print("")
        print("[VT] HOW TO SCAN A >650 MB INSTALLER:")
        print("  1. Upload every .exe/.dll/.pyd from vt_report_hashes.csv manually;")
        print("     AV engines scan each binary anyway - the big Setup.exe is just")
        print("     an LZMA container around these same files.")
        print("  2. OR publish the LITE installer instead:")
        print("        python build_installer.py --lite")
        print("     It is <650 MB and can be uploaded to VirusTotal in one click.")
        print("  3. OR use the API: set VT_API_KEY env var and re-run this script.")


if __name__ == "__main__":
    main()