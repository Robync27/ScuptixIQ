"""
MeshForge 3D — PyInstaller Build Script (AV-friendly)
======================================================
Compiles the application into a single-folder Windows executable
suitable for packaging with Inno Setup into a Setup.exe installer.

Anti-Virus false-positive hardening:
  * --onedir (NOT --onefile: packed single-file exes are the #1 VT trigger)
  * --noupx (UPX compression is flagged by dozens of AV engines)
  * Embedded Windows version resource + icon (unsigned bare exes look suspicious)
  * No packed/obfuscated payloads; plain on-disk DLLs and .pyd files

Usage:
    python build.py

Requires: pip install pyinstaller
"""

import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"

# LITE edition: exclude multi-GB AI libraries; they are pip-installed on first
# launch by app/bootstrap_deps.py. Set MF_LITE=1 to build the Lite bundle.
LITE = os.environ.get("MF_LITE", "0") == "1"
HEAVY_LIBS = ["torch", "torchvision", "transformers", "diffusers", "accelerate"]


def build() -> None:
    """Run PyInstaller to produce a single-folder executable."""
    entry_point = str(APP_DIR / "main.py")
    name = "MeshForge3D"
    dist_dir = str(ROOT / "dist")

    # Data files to bundle with the executable
    datas = [
        (str(APP_DIR / "ui"), "ui"),
        (str(ROOT / "tsr_sdk"), "tsr_sdk"),
        (str(ROOT / "installer" / "LICENSE.txt"), "licenses/LICENSE.txt"),
    ]

    # Only include models dir if it exists and is small enough to bundle
    models_dir = APP_DIR / "models"
    if models_dir.exists() and any(models_dir.iterdir()):
        datas.append((str(models_dir), "models"))

    # Filter to only existing paths
    datas = [(src, dst) for src, dst in datas if os.path.exists(src)]

    # Hidden imports required by the application
    hidden_imports = [
        "eel",
        "eel.browsers",
        "safetensors",
        "huggingface_hub",
        "rembg",
        "trimesh",
        "mcubes",
        "xatlas",
        "moderngl",
        "scipy",
        "skimage",
        "PIL",
        "numpy",
        "cv2",
    ]
    if not LITE:
        hidden_imports += HEAVY_LIBS

    # Exclude heavy/unused modules: smaller surface = fewer heuristic hits
    excludes = [
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "PyQt5",
        "PySide2",
        "PySide6",
        "pandas",
        "sympy",
        "pydoc_data",
    ]

    # Build arguments
    args = [
        entry_point,
        "--name", name,
        "--distpath", dist_dir,
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
        "--noconsole",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--noupx",                                   # critical for AV reputation
        "--icon", str(ROOT / "MeshForge3D.ico"),
        "--version-file", str(ROOT / "version_info.txt"),
        "--collect-all", "rembg",
        "--collect-all", "trimesh",
        "--collect-all", "eel",
    ]

    if not LITE:
        args.extend([
            "--collect-all", "diffusers",
            "--collect-submodules", "transformers",
        ])
    else:
        # Lite: make sure heavy libs are NOT pulled in transitively
        for lib in HEAVY_LIBS:
            args.extend(["--exclude-module", lib])

    # Add data files
    for src, dst in datas:
        args.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    # Add hidden imports
    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])

    # Add excludes
    for exc in excludes:
        args.extend(["--exclude-module", exc])

    edition = "LITE (AI libs downloaded on first run)" if LITE else "FULL (offline)"
    print(f"[Build] Edition : {edition}")
    print(f"[Build] Running PyInstaller with {len(datas)} data dirs...")
    print(f"[Build] Entry point: {entry_point}")
    print(f"[Build] Output: {dist_dir}\\{name}")

    PyInstaller.__main__.run(args)

    exe_path = Path(dist_dir) / name / f"{name}.exe"
    if not exe_path.exists():
        print("[Build][ERROR] Executable was not produced!")
        sys.exit(1)

    size_mb = sum(f.stat().st_size for f in (Path(dist_dir) / name).rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"\n[Build] Complete!")
    print(f"[Build] Executable: {exe_path}")
    print(f"[Build] Total folder size: {size_mb:.0f} MB")
    print(f"[Build] Ready for Inno Setup packaging (python build_installer.py).")


if __name__ == "__main__":
    build()