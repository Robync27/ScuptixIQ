"""
MeshForge 3D — LITE edition builder (web-installer, fits VirusTotal <650MB)
============================================================================
Instead of freezing multi-GB AI libraries, the Lite edition ships:

    runtime\\        Embedded Python 3.11 (embeddable zip) + pip, preconfigured
    app\\            Application source (Eel UI + engines)
    tsr_sdk\\        TripoSR SDK (MIT)
    requirements.txt Installed automatically on FIRST RUN (visible console)

Resulting Setup.exe is ~60-120 MB -> uploadable to VirusTotal in one click.
AI libraries (~2.5 GB) are downloaded once by the user at first launch.

Usage:
    python tools/build_lite.py            # assemble + compile installer
    python tools/build_lite.py --no-iscc  # only assemble lite_runtime/
"""

import argparse
import os
import stat
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LITE_DIR = ROOT / "lite_runtime"
PY_VER = "3.11.9"
PY_URL = f"https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
CACHE = ROOT / "tools" / "_cache"

PTH_CONTENT = """\
python311.zip
.
Lib\\site-packages
..\\app
..\\tsr_sdk
..
"""

LAUNCHER_BAT = """\
@echo off
title MeshForge 3D
cd /d "%~dp0"
if not exist ".ai_ready" (
    echo ============================================================
    echo   MeshForge 3D - first run setup
    echo   Downloading AI components (~2.5 GB, one time only)...
    echo   Please keep this window open until it finishes.
    echo ============================================================
    runtime\\python.exe -m pip install --upgrade pip
    runtime\\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Installation failed. Check your internet connection
        echo         and run this file again.
        pause
        exit /b 1
    )
    type nul > .ai_ready
    echo.
    echo Setup complete! Starting MeshForge 3D...
    timeout /t 2 >nul
)
start "" runtime\\pythonw.exe app\\main.py
"""


def _force_remove(func, path, _exc):
    """chmod + retry for read-only files (e.g. .git pack indexes)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"[Lite] Cached: {dest.name}")
        return
    print(f"[Lite] Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)


def assemble() -> None:
    if LITE_DIR.exists():
        print("[Lite] Cleaning previous lite_runtime/ ...")
        shutil.rmtree(LITE_DIR, onerror=_force_remove)

    LITE_DIR.mkdir(parents=True)
    runtime = LITE_DIR / "runtime"
    runtime.mkdir()

    # 1. Embedded Python -----------------------------------------------------
    py_zip = CACHE / f"python-{PY_VER}-embed-amd64.zip"
    download(PY_URL, py_zip)
    with zipfile.ZipFile(py_zip) as zf:
        zf.extractall(runtime)

    # Enable site-packages + project paths
    pth = runtime / f"python{PY_VER.rpartition('.')[0].replace('.', '')}._pth"
    pth.write_text(PTH_CONTENT, encoding="ascii")

    # 2. Bootstrap pip into the embedded runtime ------------------------------
    get_pip = CACHE / "get-pip.py"
    download(GET_PIP_URL, get_pip)
    print("[Lite] Bootstrapping pip into embedded runtime...")
    res = subprocess.run([str(runtime / "python.exe"), str(get_pip),
                          "--no-warn-script-location"], capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout[-800:], res.stderr[-800:])
        sys.exit("[Lite][ERROR] get-pip failed")

    # 3. Application sources ---------------------------------------------------
    # NOTE: app/models (TripoSR checkpoint) is NOT bundled - downloaded on
    # first run by app/downloader.py, keeping the installer small.
    shutil.copytree(ROOT / "app", LITE_DIR / "app",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "outputs",
                                                  ".ai_deps_ok", "models", ".env"))
    shutil.copytree(ROOT / "tsr_sdk", LITE_DIR / "tsr_sdk",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    shutil.copy2(ROOT / "requirements.txt", LITE_DIR / "requirements.txt")
    lic = ROOT / "installer" / "LICENSE.txt"
    if lic.exists():
        shutil.copy2(lic, LITE_DIR / "LICENSE.txt")
    ico = ROOT / "MeshForge3D.ico"
    if ico.exists():
        shutil.copy2(ico, LITE_DIR / "MeshForge3D.ico")

    # 4. Launcher ----------------------------------------------------------------
    (LITE_DIR / "MeshForge3D.bat").write_text(LAUNCHER_BAT, encoding="utf-8")

    size_mb = sum(f.stat().st_size for f in LITE_DIR.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"[Lite] Assembled {LITE_DIR} ({size_mb:.0f} MB)")


def compile_installer() -> None:
    sys.path.insert(0, str(ROOT))
    from build_installer import ensure_inno_setup
    iscc = ensure_inno_setup()

    print("[Lite] Compiling installer...")
    res = subprocess.run([str(iscc), str(ROOT / "installer_lite.iss")], cwd=str(ROOT))
    if res.returncode != 0:
        sys.exit("[Lite][ERROR] Inno Setup compilation failed")

    out = ROOT / "installer_output" / "MeshForge3D_Lite_Setup_v2.1.0.exe"
    if out.exists():
        mb = out.stat().st_size / (1024 * 1024)
        vt_ok = "YES (<650MB, VirusTotal-ready)" if mb < 650 else "NO (>650MB)"
        print(f"\n[Lite] DONE: {out}")
        print(f"[Lite] Size: {mb:.0f} MB — VirusTotal uploadable: {vt_ok}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-iscc", action="store_true", help="Only assemble lite_runtime/")
    args = ap.parse_args()
    assemble()
    if not args.no_iscc:
        compile_installer()