"""
MeshForge 3D — Universal Installer Build Orchestrator
======================================================
One-command pipeline:

    1. PyInstaller  -> dist\\MeshForge3D\\          (AV-friendly onedir bundle)
    2. Wizard art   -> installer\\wizard_*.bmp      (auto-generated if missing)
    3. Inno Setup   -> installer_output\\MeshForge3D_Setup_v2.1.0.exe

Inno Setup is auto-installed via winget if not found.

Optional code signing (strongly recommended for zero AV/SmartScreen flags):
    python build_installer.py --sign "C:\\Path\\signtool.exe" --cert "my.pfx" --password "..."
    or compile with:  iscc /DSignToolName="MySignTool" installer.iss

Usage:
    python build_installer.py            # full pipeline
    python build_installer.py --skip-pyinstaller   # only rebuild Setup.exe
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
ISCC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
]


# ---------------------------------------------------------------------------
# Step 2: wizard artwork (generated so the repo stays light)
# ---------------------------------------------------------------------------
def ensure_wizard_bitmaps() -> None:
    """Generate Inno Setup wizard images (164x314 side + 55x58 top) if missing."""
    side_path = ROOT / "installer" / "wizard_side.bmp"
    top_path = ROOT / "installer" / "wizard_top.bmp"
    if side_path.exists() and top_path.exists():
        return

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[Installer][WARN] Pillow missing - skipping wizard art generation.")
        return

    side_path.parent.mkdir(parents=True, exist_ok=True)

    # Side banner 164x314 — dark gradient with cyan accents
    w, h = 164, 314
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(10 + 14 * t)
        g = int(13 + 18 * t)
        b = int(20 + 30 * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    d = ImageDraw.Draw(img)
    # accent bars
    d.rectangle([0, 0, w, 4], fill=(0, 240, 255))
    d.rectangle([0, h - 4, w, h], fill=(168, 85, 247))
    # simple cube wireframe motif
    cx, cy, s = 82, 150, 46
    top = [(cx, cy - s), (cx + s, cy - s // 2), (cx, cy), (cx - s, cy - s // 2)]
    left = [(cx - s, cy - s // 2), (cx, cy), (cx, cy + s), (cx - s, cy + s // 2)]
    right = [(cx + s, cy - s // 2), (cx, cy), (cx, cy + s), (cx + s, cy + s // 2)]
    for poly in (top, left, right):
        d.polygon(poly, outline=(0, 240, 255))
    img.save(side_path, format="BMP")

    # Top-right small logo 55x58 — cyan square with dark cube
    tw, th = 55, 58
    timg = Image.new("RGB", (tw, th), (10, 13, 20))
    td = ImageDraw.Draw(timg)
    td.rectangle([0, 0, tw - 1, th - 1], outline=(0, 240, 255))
    tcx, tcy, ts = 27, 29, 16
    ttop = [(tcx, tcy - ts), (tcx + ts, tcy - ts // 2), (tcx, tcy), (tcx - ts, tcy - ts // 2)]
    tleft = [(tcx - ts, tcy - ts // 2), (tcx, tcy), (tcx, tcy + ts), (tcx - ts, tcy + ts // 2)]
    tright = [(tcx + ts, tcy - ts // 2), (tcx, tcy), (tcx, tcy + ts), (tcx + ts, tcy + ts // 2)]
    for poly in (ttop, tleft, tright):
        td.polygon(poly, outline=(0, 240, 255))
    timg.save(top_path, format="BMP")

    print(f"[Installer] Generated wizard art: {side_path.name}, {top_path.name}")


# ---------------------------------------------------------------------------
# Step 3: locate / install Inno Setup
# ---------------------------------------------------------------------------
def find_iscc() -> Optional[Path]:
    iscc = shutil.which("iscc")
    if iscc:
        return Path(iscc)
    for cand in ISCC_CANDIDATES:
        if cand.is_file():
            return cand
    return None


def ensure_inno_setup() -> Path:
    iscc = find_iscc()
    if iscc:
        print(f"[Installer] Found Inno Setup: {iscc}")
        return iscc

    print("[Installer] Inno Setup not found. Trying winget silent install...")
    winget = shutil.which("winget")
    if winget:
        res = subprocess.run(
            [winget, "install", "-e", "--id", "JRSoftware.InnoSetup", "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True,
        )
        if res.returncode == 0:
            iscc = find_iscc()
            if iscc:
                print(f"[Installer] Inno Setup installed: {iscc}")
                return iscc
        else:
            print(f"[Installer] winget failed: {res.stderr.strip()[:300]}")

    print(
        "[Installer][ERROR] Could not obtain Inno Setup automatically.\n"
        "    Install manually from https://jrsoftware.org/isdl.php and re-run."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Optional code signing
# ---------------------------------------------------------------------------
def sign_file(signtool: str, cert: str, password: str, target: Path) -> None:
    cmd = [
        signtool, "sign",
        "/fd", "SHA256",
        "/td", "SHA256",
        "/tr", "http://timestamp.digicert.com",
        "/f", cert,
        "/p", password,
        str(target),
    ]
    print(f"[Sign] Signing {target.name} ...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[Sign] OK: {target.name}")
    else:
        print(f"[Sign][WARN] Failed: {res.stdout} {res.stderr}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Build MeshForge 3D universal installer")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Reuse existing dist/MeshForge3D")
    parser.add_argument("--lite", action="store_true",
                        help="Build LITE edition (<650MB, fits VirusTotal): AI libs download on first run")
    parser.add_argument("--sign", metavar="SIGNTOOL_PATH", help="Path to signtool.exe for Authenticode signing")
    parser.add_argument("--cert", metavar="PFX_FILE", help="Code-signing certificate (.pfx)")
    parser.add_argument("--password", metavar="PASSWORD", help="Certificate password")
    args = parser.parse_args()

    exe = ROOT / "dist" / "MeshForge3D" / "MeshForge3D.exe"

    # --- Step 1: PyInstaller -------------------------------------------------
    if args.skip_pyinstaller:
        if not exe.exists():
            print(f"[ERROR] {exe} not found. Run without --skip-pyinstaller first.")
            sys.exit(1)
        print("[Installer] Skipping PyInstaller (using existing dist).")
    elif args.lite:
        # LITE edition uses its own pipeline (embedded Python + first-run deps),
        # including Inno compilation - nothing else to do here.
        print("=" * 60)
        print("  LITE edition — embedded Python web-installer")
        print("=" * 60)
        res = subprocess.run([sys.executable, str(ROOT / "tools" / "build_lite.py")])
        sys.exit(res.returncode)
    else:
        print("=" * 60)
        print("  STEP 1/3 — PyInstaller bundle")
        print("=" * 60)
        res = subprocess.run([sys.executable, str(ROOT / "build.py")])
        if res.returncode != 0 or not exe.exists():
            print("[ERROR] PyInstaller build failed.")
            sys.exit(1)

    # --- Step 2: wizard art ---------------------------------------------------
    print("=" * 60)
    print("  STEP 2/3 — Installer assets")
    print("=" * 60)
    ensure_wizard_bitmaps()

    # --- Step 3: Inno Setup ---------------------------------------------------
    print("=" * 60)
    print("  STEP 3/3 — Inno Setup compilation")
    print("=" * 60)
    iscc = ensure_inno_setup()
    setup_out = ROOT / "installer_output"
    setup_out.mkdir(exist_ok=True)

    iss_file = "installer_lite.iss" if args.lite else "installer.iss"
    res = subprocess.run([str(iscc), str(ROOT / iss_file)], cwd=str(ROOT))
    if res.returncode != 0:
        print("[ERROR] Inno Setup compilation failed.")
        sys.exit(1)

    expected_name = "MeshForge3D_Lite_Setup_v2.1.0.exe" if args.lite else "MeshForge3D_Setup_v2.1.0.exe"
    setup_exe = setup_out / expected_name
    if not setup_exe.exists():
        candidates = sorted(setup_out.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
        setup_exe = candidates[0] if candidates else None

    # --- Optional signing ------------------------------------------------------
    if args.sign and args.cert and setup_exe:
        sign_file(args.sign, args.cert, args.password or "", setup_exe)

    size_mb = setup_exe.stat().st_size / (1024 * 1024) if setup_exe else 0
    print()
    print("=" * 60)
    print("  BUILD COMPLETE")
    print("=" * 60)
    if setup_exe:
        print(f"  Installer : {setup_exe}")
        print(f"  Size      : {size_mb:.0f} MB")
    print("""
  VirusTotal checklist:
   [x] onedir bundle, no UPX packing, no single-file self-extract
   [x] version resource + icon embedded into MeshForge3D.exe
   [x] Setup.exe has version info, icon, EULA page
   [ ] Upload to https://virustotal.com and check remaining detections
   [ ] For ZERO detections & no SmartScreen warning: buy an OV/EV code-signing
       certificate (Certum ~$70/yr, Sectigo EV ~$250/yr) and re-run with:
         python build_installer.py --skip-pyinstaller --sign <signtool> --cert <pfx> --password <pw>
""")


if __name__ == "__main__":
    main()