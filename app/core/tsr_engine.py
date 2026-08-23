"""
MeshForge 3D — Universal 3D Reconstruction Engine (TSREngine)
==============================================================
Provides high-performance image-to-3D generation across NVIDIA GPUs (CUDA),
AMD / Intel GPUs, and multi-core CPUs.
"""

import gc
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import torch
import trimesh
import trimesh.smoothing
from PIL import Image

# Ensure tsr_sdk is in python path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TSR_SDK = _PROJECT_ROOT / "tsr_sdk"
if str(_TSR_SDK) not in sys.path:
    sys.path.insert(0, str(_TSR_SDK))

from tsr.system import TSR
from tsr.bake_texture import bake_texture
from tsr.utils import to_gradio_3d_orientation


class TSREngine:
    """Manages the TripoSR model lifecycle and 3D inference pipeline."""

    def __init__(self, model_dir: Optional[str] = None) -> None:
        if model_dir is None:
            model_dir = str(_PROJECT_ROOT / "app" / "models")
        self.model_dir: str = model_dir
        self.model: Optional[TSR] = None
        self.active_device: str = "cpu"
        self._is_loaded: bool = False

    @staticmethod
    def get_hardware_info() -> Dict[str, Any]:
        """Detect and return detailed information on available hardware acceleration."""
        has_cuda = torch.cuda.is_available()
        cuda_devices = []
        if has_cuda:
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                mem = round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 1)
                cuda_devices.append({"id": f"cuda:{i}", "name": f"{name} ({mem} GB)", "vram_gb": mem})

        import platform
        cpu_name = platform.processor() or platform.machine()
        threads = torch.get_num_threads()

        best_device = "cuda:0" if has_cuda else "cpu"

        return {
            "has_cuda": has_cuda,
            "cuda_devices": cuda_devices,
            "best_device": best_device,
            "cpu_info": f"{cpu_name} ({threads} threads)",
            "torch_version": torch.__version__,
        }

    def _resolve_device(self, target_device: str) -> str:
        """Resolve 'auto' or device string to valid torch device."""
        if target_device.lower() in ("auto", "best"):
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        if target_device.startswith("cuda"):
            return target_device if torch.cuda.is_available() else "cpu"
        return "cpu"

    def load(self, device: str = "auto") -> None:
        """Load the TripoSR model weights into memory on the target device."""
        resolved_device = self._resolve_device(device)
        print(f"[TSREngine] Loading model on {resolved_device} from {self.model_dir}...")
        t0 = time.time()

        config_path = os.path.join(self.model_dir, "config.yaml")
        ckpt_path = os.path.join(self.model_dir, "model.ckpt")

        if os.path.isfile(config_path) and os.path.isfile(ckpt_path):
            self.model = TSR.from_pretrained(
                self.model_dir,
                config_name="config.yaml",
                weight_name="model.ckpt",
            )
        else:
            # Fallback to HuggingFace repository download if local checkpoint is absent
            print("[TSREngine] Local checkpoint not found. Fetching from stabilityai/TripoSR...")
            self.model = TSR.from_pretrained(
                "stabilityai/TripoSR",
                config_name="config.yaml",
                weight_name="model.ckpt",
            )

        self.model.to(resolved_device)
        self.model.eval()
        self.active_device = resolved_device
        self._is_loaded = True
        print(f"[TSREngine] Model loaded in {time.time() - t0:.2f}s on {resolved_device}.")

    def set_device(self, device: str) -> None:
        """Switch device between CUDA and CPU."""
        resolved_device = self._resolve_device(device)
        if self.model is not None and resolved_device != self.active_device:
            print(f"[TSREngine] Moving model from {self.active_device} to {resolved_device}...")
            self.model.to(resolved_device)
            self.active_device = resolved_device
            if "cuda" in resolved_device:
                torch.cuda.empty_cache()
            gc.collect()

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded and self.model is not None

    def generate(
        self,
        image_pil: Image.Image,
        resolution: int = 256,
        texture_mode: str = "uv_atlas",
        bake_uv_texture: bool = True,
        texture_resolution: int = 1024,
        chunk_size: int = 8192,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> Tuple[Any, Optional[Dict[str, Any]], float]:
        """
        Generate a 3D mesh from an input PIL image.
        Supports texture_mode: 'uv_atlas' (baked PBR texture), 'vertex_colors' (fast preview), 'none' (pure geometry / clay).
        """
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call .load() first.")

        t_start = time.time()

        is_none_mode = (texture_mode == "none" or texture_mode == "clay")
        should_bake_uv = (texture_mode == "uv_atlas") and not is_none_mode
        has_vertex_color = (texture_mode == "vertex_colors") and not is_none_mode

        # Step 1: Neural Image-to-Triplane Inference
        if progress_cb:
            progress_cb("Neural Feature Extraction", 0.3)

        self.model.renderer.set_chunk_size(chunk_size)

        with torch.no_grad():
            scene_codes = self.model([image_pil], device=self.active_device)

        # Step 2: Isosurface Marching Cubes Mesh Extraction
        if progress_cb:
            progress_cb("Marching Cubes Mesh Extraction", 0.6)

        with torch.no_grad():
            meshes = self.model.extract_mesh(
                scene_codes,
                has_vertex_color=has_vertex_color,
                resolution=resolution,
            )

        mesh = meshes[0]
        bake_output = None

        # Clean and smooth mesh BEFORE UV parameterization so vertex indices match 100%
        try:
            if hasattr(mesh, "remove_unreferenced_vertices"):
                mesh.remove_unreferenced_vertices()
            if hasattr(mesh, "remove_infinite_values"):
                mesh.remove_infinite_values()

            # Remove small disconnected floating debris
            components = mesh.split(only_watertight=False)
            if len(components) > 1:
                max_faces = max(len(c.faces) for c in components)
                valid = [c for c in components if len(c.faces) >= max(30, int(max_faces * 0.02))]
                if valid:
                    mesh = trimesh.util.concatenate(valid)

            # Smooth Marching Cubes staircase noise without volume shrinkage
            import trimesh.smoothing
            mesh = trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.52, iterations=4)
            mesh.fix_normals(multibody=True)
        except Exception as exc:
            print(f"[TSREngine] Pre-baking mesh cleanup notice: {exc}")

        # Step 3: Optional UV Texture Baking (Must query in native unrotated TripoSR space)
        if should_bake_uv:
            if progress_cb:
                progress_cb("Baking UV Texture Atlas", 0.8)

            try:
                bake_output = bake_texture(
                    mesh, self.model, scene_codes[0], texture_resolution
                )
            except Exception as exc:
                print(f"[TSREngine] UV Baking failed: {exc}, falling back to vertex colors.")
                traceback.print_exc()
                bake_output = None

        # Transform mesh coordinates to standard glTF space (+Y Up, +X Right, +Z Front)
        mesh = self.orient_mesh_for_gltf(mesh)

        elapsed = time.time() - t_start

        if progress_cb:
            progress_cb("Finalizing 3D Geometry", 1.0)

        # Clean cache
        if "cuda" in self.active_device:
            torch.cuda.empty_cache()

        return mesh, bake_output, elapsed

    @staticmethod
    def orient_mesh_for_gltf(mesh: "trimesh.Trimesh") -> "trimesh.Trimesh":
        """Convert from TripoSR coordinates (Z up, X back, Y right) to standard glTF (Y up, X right, Z front)."""
        x = mesh.vertices[:, 0].copy()
        y = mesh.vertices[:, 1].copy()
        z = mesh.vertices[:, 2].copy()
        mesh.vertices[:, 0] = y
        mesh.vertices[:, 1] = z
        mesh.vertices[:, 2] = -x
        return mesh

    def unload(self) -> None:
        """Free model memory."""
        if self.model is not None:
            del self.model
            self.model = None
            self._is_loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        print("[TSREngine] Model unloaded.")
