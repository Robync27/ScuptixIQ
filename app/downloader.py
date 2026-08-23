"""
MeshForge 3D — Asset Downloader
=================================
Downloads SF3D model from HuggingFace and exports to ONNX automatically.
First-run setup: downloads PyTorch weights, exports to ONNX via torch.onnx.

Zero PyTorch at inference time. PyTorch is only used during this one-time
export step (run once, then the ONNX file is used for all future inference).
"""
import os
import sys
import traceback
from pathlib import Path
from typing import Callable, List, Optional

# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_APP_DIR = _THIS_FILE.parent
_PROJECT_ROOT = _APP_DIR.parent

# Default HuggingFace repository for SF3D
DEFAULT_REPO = "stabilityai/stable-fast-3d"

# HuggingFace token is NOT embedded (security): set HF_TOKEN env var if you
# need access to a gated model. Public TripoSR checkpoint needs no token.
_HF_TOKEN = ""

# Alternative repos
FALLBACK_REPOS: List[str] = []

# Required files to check for
REQUIRED_ONNX_FILES = [
    "model.onnx",
    "sf3d_model.onnx",
    "sf3d.onnx",
]

# ONNX export constants
MAX_VERTS = 65536
MAX_FACES = 65536
TEX_SIZE = 1024
INPUT_SIZE = 512


class AssetDownloader:
    """Downloads SF3D model and exports to ONNX automatically.

    Callback signature:
        callback(phase: str, progress: float, message: str)
        phase  = 'download' | 'export' | 'complete' | 'error'
        progress = 0.0 – 1.0
        message  = human-readable status string
    """

    def __init__(self, callback: Optional[Callable] = None) -> None:
        self.callback = callback

    # ------------------------------------------------------------------
    def _emit(self, phase: str, progress: float, message: str) -> None:
        if self.callback:
            try:
                self.callback(phase, progress, message)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def download_huggingface(
        self,
        target_dir: str,
        repo_id: str = DEFAULT_REPO,
    ) -> bool:
        """Download SF3D model from HuggingFace and export to ONNX.

        Steps:
        1. Try to find pre-compiled .onnx files.
        2. If no .onnx found, download PyTorch model and export to ONNX
           using torch.onnx.export().
        3. Save model.onnx to target_dir.

        Returns:
            True if ONNX model is ready, False otherwise.
        """
        os.makedirs(target_dir, exist_ok=True)

        # Step 1: Try pre-compiled ONNX
        self._emit("download", 0.0, "Checking for pre-compiled ONNX model...")
        if self._try_download_onnx(target_dir, repo_id):
            return True

        # Step 2: Try local safetensors file first
        self._emit("download", 0.05, "Looking for local model.safetensors...")
        if self._try_local_safetensors(target_dir):
            return True

        # Step 3: Download PyTorch model + export to ONNX
        self._emit("download", 0.05, "Downloading SF3D PyTorch model...")
        print("[Downloader] No pre-compiled ONNX found. Will download PyTorch model and export.")

        try:
            self._download_and_export(target_dir, repo_id)
            return True
        except Exception as exc:
            traceback.print_exc()
            msg = (
                f"Failed to download and export SF3D model.\n"
                f"Error: {exc}\n\n"
                f"Please run manually:\n"
                f"  python scripts/export_sf3d_onnx.py --output app/models/model.onnx"
            )
            self._emit("error", 0.0, msg)
            print(f"[Downloader] {msg}")
            return False

    # ------------------------------------------------------------------
    def _try_download_onnx(self, target_dir: str, repo_id: str) -> bool:
        """Try to find pre-compiled .onnx files in HF repos."""
        from huggingface_hub import snapshot_download

        repos_to_try = [repo_id] + FALLBACK_REPOS
        for repo in repos_to_try:
            self._emit("download", 0.02, f"Trying {repo}...")
            print(f"[Downloader] Trying repository: {repo}")
            try:
                snapshot_download(
                    repo_id=repo,
                    local_dir=target_dir,
                    revision="main",
                    allow_patterns=["*.onnx"],
                    resume_download=True,
                )
                if self._has_onnx_file(target_dir):
                    self._emit("complete", 1.0, "ONNX model downloaded!")
                    print(f"[Downloader] ONNX model saved to {target_dir}")
                    return True
            except Exception as exc:
                print(f"[Downloader] {repo}: {exc}")
                continue

        return False

    # ------------------------------------------------------------------
    def _download_and_export(self, target_dir: str, repo_id: str) -> None:
        """Download PyTorch SF3D model and export to ONNX."""
        import torch
        import numpy as np

        self._emit("download", 0.1, "Loading SF3D model from HuggingFace...")
        print("[Downloader] Loading SF3D PyTorch model...")

        # Load the model
        model = self._load_sf3d_model(repo_id)
        if model is None:
            raise RuntimeError(f"Could not load SF3D model from {repo_id}")

        self._emit("export", 0.4, "Exporting to ONNX (this may take several minutes)...")
        print("[Downloader] Exporting to ONNX...")

        output_path = os.path.join(target_dir, "model.onnx")

        # Build export wrapper
        wrapper = _ONNXModule(model)
        wrapper.eval()

        dummy = torch.randn(1, 4, INPUT_SIZE, INPUT_SIZE, dtype=torch.float32)

        # Test forward pass
        self._emit("export", 0.5, "Testing forward pass...")
        with torch.no_grad():
            outputs = wrapper(dummy)
            print(f"[Downloader] Forward pass OK. "
                  f"verts={outputs[0].shape}, faces={outputs[1].shape}")

        # Export
        self._emit("export", 0.6, "Tracing ONNX graph...")
        torch.onnx.export(
            wrapper,
            dummy,
            output_path,
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=["input"],
            output_names=[
                "vertices", "faces", "uvs", "texture", "vert_count", "face_count"
            ],
            dynamic_axes={
                "input": {0: "batch"},
                "vertices": {0: "batch"},
                "faces": {0: "batch"},
                "uvs": {0: "batch"},
                "texture": {0: "batch"},
                "vert_count": {0: "batch"},
                "face_count": {0: "batch"},
            },
        )

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        self._emit("complete", 1.0, f"ONNX model ready ({size_mb:.0f} MB)!")
        print(f"[Downloader] ONNX model exported: {output_path} ({size_mb:.1f} MB)")

    # ------------------------------------------------------------------
    def _load_sf3d_model(self, repo_id: str):
        """Load SF3D model from HuggingFace.

        The SF3D model uses a custom TripoSR architecture (tsr.*), not
        standard transformers. We load it via the local TripoSR SDK.
        """
        import torch

        token = os.environ.get("HF_TOKEN", _HF_TOKEN)
        os.environ["HF_TOKEN"] = token

        # Ensure TripoSR SDK is on path
        self._ensure_tsr_sdk()

        try:
            from tsr.system import TSR
            model = TSR.from_pretrained(repo_id, config_name="config.json", weight_name="model.ckpt")
            model.eval()
            print("[Downloader] Loaded via TripoSR SDK.")
            return model
        except Exception as exc:
            print(f"[Downloader] Failed to load via TripoSR SDK: {exc}")
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    def _try_local_safetensors(self, target_dir: str) -> bool:
        """Try to load a local SF3D model and export to ONNX.

        Priority order:
          1. app/models/ (model.ckpt + config.yaml) — complete SF3D checkpoint
          2. <project_root>/model.safetensors (only if config present)
          3. <target_dir>/model.safetensors (only if config present)

        Requires config.json or config.yaml in the same directory.
        Does NOT attempt to download missing configs — just skips.
        """
        import torch

        # Priority 1: app/models/ with model.ckpt + config.yaml
        models_dir = _PROJECT_ROOT / "app" / "models"
        ckpt_path = models_dir / "model.ckpt"
        config_yaml = models_dir / "config.yaml"
        config_json = models_dir / "config.json"

        if ckpt_path.is_file() and (config_yaml.is_file() or config_json.is_file()):
            model_dir = str(models_dir)
            print(f"[Downloader] Found local SF3D model in {model_dir}")
            print(f"  Checkpoint: {ckpt_path} ({ckpt_path.stat().st_size / 1e9:.1f} GB)")
            if config_yaml.is_file():
                print(f"  Config: config.yaml")
            if config_json.is_file():
                print(f"  Config: config.json")

            self._emit("export", 0.1, "Loading local SF3D model...")
            print("[Downloader] Loading model from local checkpoint...")

            try:
                model = self._load_local_checkpoint(model_dir)
                if model is None:
                    return False
            except Exception as exc:
                print(f"[Downloader] Failed to load local model: {exc}")
                traceback.print_exc()
                return False

            self._emit("export", 0.4, "Exporting to ONNX (this may take several minutes)...")
            print("[Downloader] Exporting to ONNX from local checkpoint...")

            output_path = os.path.join(target_dir, "model.onnx")
            self._export_model_to_onnx(model, output_path)
            return True

        # Priority 2 & 3: model.safetensors (only if config present)
        candidates = [
            _PROJECT_ROOT / "model.safetensors",
            Path(target_dir) / "model.safetensors",
        ]

        for safetensors_path in candidates:
            if not safetensors_path.is_file():
                continue

            model_dir = str(safetensors_path.parent)
            has_config = (
                os.path.isfile(os.path.join(model_dir, "config.json"))
                or os.path.isfile(os.path.join(model_dir, "config.yaml"))
            )
            if not has_config:
                print(f"[Downloader] Skipping {safetensors_path} — no config.json/config.yaml alongside.")
                continue

            print(f"[Downloader] Found local safetensors: {safetensors_path}")

            self._emit("export", 0.1, "Loading local safetensors model...")
            print("[Downloader] Loading model from local safetensors...")

            try:
                model = self._load_local_checkpoint(model_dir)
                if model is None:
                    continue
            except Exception as exc:
                print(f"[Downloader] Failed to load local model: {exc}")
                traceback.print_exc()
                continue

            self._emit("export", 0.4, "Exporting to ONNX (this may take several minutes)...")
            print("[Downloader] Exporting to ONNX from local safetensors...")

            output_path = os.path.join(target_dir, "model.onnx")
            self._export_model_to_onnx(model, output_path)
            return True

        print("[Downloader] No local model found (no model.ckpt or model.safetensors with config).")
        return False

    # ------------------------------------------------------------------
    def _load_local_checkpoint(self, model_dir: str):
        """Load a local TripoSR checkpoint (model.ckpt or model.safetensors).

        Uses the TripoSR SDK (tsr.system.TripoSR) to load the model.
        Falls back to direct torch.load if SDK is unavailable.
        """
        import torch

        # Ensure SDK is on path
        self._ensure_tsr_sdk()

        # Try TripoSR SDK first
        try:
            from tsr.system import TSR
            model = TSR.from_pretrained(model_dir, config_name="config.json", weight_name="model.ckpt")
            model.eval()
            print("[Downloader] Loaded via TripoSR SDK from local dir.")
            return model
        except Exception as exc:
            print(f"[Downloader] TripoSR SDK failed: {exc}")
            traceback.print_exc()

        # Fallback: direct torch.load
        ckpt_path = os.path.join(model_dir, "model.ckpt")
        if os.path.isfile(ckpt_path):
            print("[Downloader] Attempting direct torch.load of model.ckpt...")
            try:
                checkpoint = torch.load(ckpt_path, map_location="cpu")
                if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                    # Lightning checkpoint — need to reconstruct model
                    print("[Downloader] Lightning checkpoint detected. "
                          "Need TripoSR SDK to reconstruct model.")
                    return None
                # Raw model
                checkpoint.eval()
                print("[Downloader] Loaded via torch.load.")
                return checkpoint
            except Exception as exc:
                print(f"[Downloader] torch.load failed: {exc}")
                traceback.print_exc()

        return None

    # ------------------------------------------------------------------
    def _export_model_to_onnx(self, model, output_path: str) -> None:
        """Export a loaded PyTorch model to ONNX."""
        import torch
        import numpy as np

        wrapper = _ONNXModule(model)
        wrapper.eval()

        dummy = torch.randn(1, 4, INPUT_SIZE, INPUT_SIZE, dtype=torch.float32)

        self._emit("export", 0.5, "Testing forward pass...")
        with torch.no_grad():
            outputs = wrapper(dummy)
            print(f"[Downloader] Forward pass OK. "
                  f"verts={outputs[0].shape}, faces={outputs[1].shape}")

        self._emit("export", 0.6, "Tracing ONNX graph...")
        torch.onnx.export(
            wrapper,
            dummy,
            output_path,
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=["input"],
            output_names=[
                "vertices", "faces", "uvs", "texture", "vert_count", "face_count"
            ],
            dynamic_axes={
                "input": {0: "batch"},
                "vertices": {0: "batch"},
                "faces": {0: "batch"},
                "uvs": {0: "batch"},
                "texture": {0: "batch"},
                "vert_count": {0: "batch"},
                "face_count": {0: "batch"},
            },
        )

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        self._emit("complete", 1.0, f"ONNX model ready ({size_mb:.0f} MB)!")
        print(f"[Downloader] ONNX model exported: {output_path} ({size_mb:.1f} MB)")

    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_tsr_sdk() -> None:
        """Add the local TripoSR SDK to sys.path if available."""
        tsr_path = _PROJECT_ROOT / "tsr_sdk"
        if tsr_path.is_dir() and str(tsr_path) not in sys.path:
            sys.path.insert(0, str(tsr_path))
            print(f"[Downloader] Added TripoSR SDK from {tsr_path}")

    # ------------------------------------------------------------------
    @staticmethod
    def _has_onnx_file(directory: str) -> bool:
        for fname in REQUIRED_ONNX_FILES:
            if os.path.isfile(os.path.join(directory, fname)):
                return True
        return False

    # ------------------------------------------------------------------
    @staticmethod
    def check_assets(
        asset_dir: str,
        required_files: Optional[List[str]] = None,
    ) -> bool:
        """Return True if at least one ONNX model file exists."""
        if required_files is None:
            required_files = REQUIRED_ONNX_FILES

        for fname in required_files:
            path = os.path.join(asset_dir, fname)
            if os.path.isfile(path):
                print(f"[Downloader] Found: {path}")
                return True

        if os.path.isdir(asset_dir):
            for entry in os.listdir(asset_dir):
                if entry.endswith(".onnx"):
                    print(f"[Downloader] Found: {entry}")
                    return True

        print("[Downloader] No ONNX model files found.")
        return False


# ---------------------------------------------------------------------------
# SF3D ONNX Export Wrapper (nn.Module for torch.onnx.export)
# ---------------------------------------------------------------------------
import torch.nn as nn


class _ONNXModule(nn.Module):
    """torch.nn.Module wrapper for ONNX export with fixed-size outputs.

    Input:  (B, 4, 512, 512) RGBA float32
    Output: (vertices, faces, uvs, texture, vert_count, face_count)
    """
    def __init__(self, sf3d_model):
        super().__init__()
        self.sf3d_model = sf3d_model

    def forward(self, image):
        import torch
        import torch.nn.functional as F

        batch = image.shape[0]
        device = image.device

        result = self.sf3d_model(image)

        if isinstance(result, dict):
            vertices = result.get("vertices", result.get("verts"))
            faces = result.get("faces", result.get("tris"))
            uvs = result.get("uvs", result.get("uv"))
            texture = result.get("texture", result.get("tex"))
        elif isinstance(result, (tuple, list)):
            vertices, faces = result[0], result[1]
            uvs = result[2] if len(result) > 2 else None
            texture = result[3] if len(result) > 3 else None
        else:
            vertices = getattr(result, "vertices", getattr(result, "verts", None))
            faces = getattr(result, "faces", getattr(result, "tris", None))
            uvs = getattr(result, "uvs", getattr(result, "uv", None))
            texture = getattr(result, "texture", getattr(result, "tex", None))

        if vertices is None or faces is None:
            raise RuntimeError("SF3D model did not return vertices/faces.")

        if vertices.ndim == 2:
            vertices = vertices.unsqueeze(0)
        if faces.ndim == 2:
            faces = faces.unsqueeze(0)

        vert_count = torch.tensor([vertices.shape[1]], dtype=torch.int64, device=device)
        face_count = torch.tensor([faces.shape[1]], dtype=torch.int64, device=device)

        if vertices.shape[1] < MAX_VERTS:
            pad_v = torch.zeros(batch, MAX_VERTS - vertices.shape[1], 3,
                                dtype=vertices.dtype, device=device)
            vertices = torch.cat([vertices, pad_v], dim=1)
        else:
            vertices = vertices[:, :MAX_VERTS, :]

        if faces.shape[1] < MAX_FACES:
            pad_f = torch.zeros(batch, MAX_FACES - faces.shape[1], 3,
                                dtype=faces.dtype, device=device)
            faces = torch.cat([faces, pad_f], dim=1)
        else:
            faces = faces[:, :MAX_FACES, :]

        if uvs is None:
            uvs = torch.zeros(batch, MAX_VERTS, 2, dtype=torch.float32, device=device)
        else:
            if uvs.ndim == 2:
                uvs = uvs.unsqueeze(0)
            if uvs.shape[1] < MAX_VERTS:
                pad_u = torch.zeros(batch, MAX_VERTS - uvs.shape[1], 2,
                                    dtype=uvs.dtype, device=device)
                uvs = torch.cat([uvs, pad_u], dim=1)
            else:
                uvs = uvs[:, :MAX_VERTS, :2]

        if texture is None:
            texture = torch.zeros(batch, 3, TEX_SIZE, TEX_SIZE,
                                  dtype=torch.float32, device=device)
        else:
            if texture.ndim == 3:
                texture = texture.unsqueeze(0)
            if texture.shape[-2] != TEX_SIZE or texture.shape[-1] != TEX_SIZE:
                texture = F.interpolate(texture, size=(TEX_SIZE, TEX_SIZE),
                                        mode="bilinear", align_corners=False)
            if texture.shape[1] == 4:
                texture = texture[:, :3, :, :]
            elif texture.shape[1] == 1:
                texture = texture.repeat(1, 3, 1, 1)

        return vertices, faces, uvs, texture, vert_count, face_count