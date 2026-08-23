"""
MeshForge 3D — First-run AI dependencies bootstrap (Lite edition)
==================================================================
The Lite installer ships without multi-GB AI libraries (torch, diffusers,
transformers). On first launch this module detects what is missing and
installs it via pip into the user's environment, showing a visible console
window so the user sees real progress.

The Full (offline) edition bundles everything and skips this entirely.
"""

import os
import subprocess
import sys

# package-import-name -> pip requirement
AI_PACKAGES = [
    ("torch", "torch>=2.0.0"),
    ("torchvision", "torchvision>=0.15.0"),
    ("transformers", "transformers>=4.30.0"),
    ("diffusers", "diffusers>=0.27.0"),
    ("accelerate", "accelerate>=0.27.0"),
    ("safetensors", "safetensors>=0.3.0"),
    ("huggingface_hub", "huggingface-hub>=0.20.0"),
]

_MARKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ai_deps_ok")


def _missing() -> list:
    out = []
    for import_name, requirement in AI_PACKAGES:
        try:
            __import__(import_name)
        except Exception:
            out.append(requirement)
    return out


def ensure_ai_deps(force_check: bool = False) -> bool:
    """Install missing AI packages. Returns True when everything is importable."""
    if not force_check and os.path.exists(_MARKER):
        return True

    missing = _missing()
    if not missing:
        try:
            open(_MARKER, "w").close()
        except OSError:
            pass
        return True

    # CUDA-aware default: let pip resolve the standard wheels.
    # (Users with NVIDIA GPUs get CUDA builds automatically on Linux;
    #  on Windows the CPU+CUDA unified wheel is installed.)
    pip_args = [sys.executable, "-m", "pip", "install", "--upgrade"] + missing

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE  # visible progress window

    print("[Setup] First run: downloading AI engine components (~2.5 GB)...")
    print("[Setup] A separate window shows download progress. This happens only once.")
    res = subprocess.run(pip_args, creationflags=creationflags)
    if res.returncode != 0:
        return False

    if not _missing():
        try:
            open(_MARKER, "w").close()
        except OSError:
            pass
        return True
    return False


if __name__ == "__main__":
    ok = ensure_ai_deps(force_check=True)
    sys.exit(0 if ok else 1)