"""Run the optional Hunyuan3D-2mv engine in its own Python environment."""

import base64
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

VIEWS = ("front", "back", "left", "right")

# The desktop app may be frozen. The worker runs in the separately installed
# CUDA environment, so its imports cannot change the desktop app's dependencies.
_WORKER = r"""
from pathlib import Path
import sys

import torch
from PIL import Image, ImageOps
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

job = Path(sys.argv[1])
resolution = int(sys.argv[2])
remove_bg = sys.argv[3] == "1"
device = sys.argv[4]
if not torch.cuda.is_available() or torch.device(device).index >= torch.cuda.device_count():
    raise RuntimeError("Multi-Image requires a CUDA-enabled PyTorch installation and an available NVIDIA GPU.")

if remove_bg:
    from hy3dgen.rembg import BackgroundRemover
    remover = BackgroundRemover()

views = {}
for path in job.glob("*.image"):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
    if remove_bg and image.getchannel("A").getextrema() == (255, 255):
        image = remover(image.convert("RGB"))
    views[path.stem] = image

pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
    "tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv",
    variant="fp16", use_safetensors=True, device=device,
)
mesh = pipeline(
    image=views, num_inference_steps=50, octree_resolution=resolution,
    num_chunks=8000, generator=torch.Generator().manual_seed(12345),
    output_type="trimesh",
)[0]
if mesh is None or mesh.is_empty:
    raise RuntimeError("Hunyuan3D-2mv did not generate a mesh.")
mesh.export(str(job / "mesh.glb"))
"""


def runtime_paths():
    """Locate the upstream source checkout and its dedicated interpreter."""
    root = os.environ.get("SCUPTIXIQ_HUNYUAN_ROOT")
    if not root:
        raise RuntimeError("Set SCUPTIXIQ_HUNYUAN_ROOT to your Hunyuan3D-2 checkout and restart ScuptixIQ. See the README setup steps.")
    root = Path(root).expanduser().resolve()
    if not (root / "hy3dgen" / "shapegen").is_dir():
        raise RuntimeError("SCUPTIXIQ_HUNYUAN_ROOT must point to a Hunyuan3D-2 source checkout.")
    default_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python = Path(os.environ.get("SCUPTIXIQ_HUNYUAN_PYTHON", str(default_python))).expanduser().absolute()
    if not python.is_file():
        raise RuntimeError("Hunyuan Python was not found. Create the checkout's .venv or set SCUPTIXIQ_HUNYUAN_PYTHON.")
    return root, python


def generate_mesh(views, resolution, remove_bg, device, runtime):
    """Condition one generation on all supplied views and return one mesh."""
    import trimesh

    root, python = runtime
    cache = root / ".scuptixiq-cache"
    cache.mkdir(exist_ok=True)
    env = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH"):
        env.pop(name, None)
    env["HF_HOME"] = str(cache / "huggingface")
    env["HF_HUB_CACHE"] = str(cache / "huggingface" / "hub")
    env["HY3DGEN_MODELS"] = str(cache / "hy3dgen")
    env["U2NET_HOME"] = str(cache / "rembg")
    env["TMP"] = env["TEMP"] = env["TMPDIR"] = str(cache)

    with TemporaryDirectory(prefix="views-", dir=cache) as temp:
        job = Path(temp)
        for view in VIEWS:
            if view in views:
                data_url = views[view]
                if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
                    raise ValueError(f"Choose a valid image for the {view} view.")
                (job / f"{view}.image").write_bytes(base64.b64decode(data_url.partition(",")[2], validate=True))

        try:
            result = subprocess.run(
                [str(python), "-c", _WORKER, str(job), str(resolution), str(int(remove_bg)), device],
                cwd=root, env=env, capture_output=True, encoding="utf-8", errors="replace",
                timeout=3600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Hunyuan3D-2mv timed out after one hour.") from exc
        if result.returncode:
            lines = (result.stderr.strip() or result.stdout.strip()).splitlines()
            detail = lines[-1] if lines else f"exit code {result.returncode}"
            raise RuntimeError(f"Hunyuan3D-2mv failed: {detail}")
        mesh = trimesh.load_mesh(str(job / "mesh.glb"), process=False)
        if mesh.is_empty:
            raise RuntimeError("Hunyuan3D-2mv returned an empty mesh.")
        return mesh
