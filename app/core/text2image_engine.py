"""
MeshForge 3D — Open-Source Text-to-Image Engine
================================================
Generates concept images from a text prompt using open-source diffusion
models (Hugging Face `diffusers`), then feeds them directly into the
image-to-3D reconstruction pipeline.

Supported models (all free / open weights):
  - sd15        : stable-diffusion-v1-5/stable-diffusion-v1-5
                  (CreativeML OpenRAIL-M — commercial use allowed)
  - dreamshaper : Lykon/dreamshaper-8
                  (CreativeML OpenRAIL-M — great object quality, fast)
  - sdxl-turbo  : stabilityai/sdxl-turbo
                  (Stability AI Community License — near-instant, GPU only)
  - sd-turbo    : stabilityai/sd-turbo
                  (Stability AI Community License — fast, low VRAM)

The engine is fully lazy: weights are downloaded on first use and cached in
the standard Hugging Face cache (~/.cache/huggingface).
"""

import gc
import os
import threading
import time
from typing import Any, Callable, Dict, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
T2I_MODELS: Dict[str, Dict[str, Any]] = {
    "sd15": {
        "repo_id": "stable-diffusion-v1-5/stable-diffusion-v1-5",
        "label": "SD 1.5 (OpenRAIL, CPU-friendly)",
        "steps": 25,
        "guidance": 7.5,
        "turbo": False,
        "min_vram_gb": 4,
    },
    "dreamshaper": {
        "repo_id": "Lykon/dreamshaper-8",
        "label": "DreamShaper 8 (best objects)",
        "steps": 25,
        "guidance": 7.0,
        "turbo": False,
        "min_vram_gb": 4,
    },
    "sd-turbo": {
        "repo_id": "stabilityai/sd-turbo",
        "label": "SD-Turbo (1-step, fast)",
        "steps": 1,
        "guidance": 0.0,
        "turbo": True,
        "min_vram_gb": 6,
    },
    "sdxl-turbo": {
        "repo_id": "stabilityai/sdxl-turbo",
        "label": "SDXL-Turbo (1-step, highest quality)",
        "steps": 1,
        "guidance": 0.0,
        "turbo": True,
        "min_vram_gb": 8,
    },
}

DEFAULT_MODEL = "dreamshaper"

# Suffix appended to user prompts so the produced image is ideal input for
# image-to-3D reconstruction (isolated object, clean background, full view).
_3D_QUALITY_SUFFIX = (
    ", single centered object, full object visible, plain light gray "
    "background, soft studio lighting, product shot, high detail, sharp focus"
)

_DEFAULT_NEGATIVE = (
    "blurry, cropped, cut off, multiple objects, cluttered background, "
    "text, watermark, low quality, deformed"
)


class Text2ImageEngine:
    """Lazy-loading wrapper around Hugging Face diffusers pipelines."""

    def __init__(self) -> None:
        self._pipe = None
        self._loaded_model_key: Optional[str] = None
        self._device: Optional[str] = None
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        return self._pipe is not None

    @property
    def loaded_model(self) -> Optional[str]:
        return self._loaded_model_key

    @staticmethod
    def list_models() -> Dict[str, Dict[str, Any]]:
        return T2I_MODELS

    @staticmethod
    def get_hardware_info() -> Dict[str, Any]:
        try:
            import torch

            has_cuda = torch.cuda.is_available()
            gpus = []
            if has_cuda:
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpus.append({
                        "name": props.name,
                        "vram_gb": round(props.total_memory / (1024 ** 3), 1),
                    })
            return {
                "has_cuda": has_cuda,
                "cuda_devices": gpus,
                "torch_version": torch.__version__,
            }
        except Exception as exc:  # pragma: no cover
            return {"has_cuda": False, "cuda_devices": [], "error": str(exc)}

    @staticmethod
    def check_diffusers_installed() -> bool:
        try:
            import diffusers  # noqa: F401
            import accelerate  # noqa: F401
            return True
        except Exception:
            return False

    def load(self, model_key: str = DEFAULT_MODEL,
             progress_cb: Optional[Callable[[str, float], None]] = None) -> str:
        """Load a pipeline onto the best available device. Returns device."""
        with self._lock:
            if self._pipe is not None and self._loaded_model_key == model_key:
                return self._device or "cpu"

            import torch
            from diffusers import StableDiffusionPipeline, AutoPipelineForText2Image

            spec = T2I_MODELS.get(model_key, T2I_MODELS[DEFAULT_MODEL])
            model_key = model_key if model_key in T2I_MODELS else DEFAULT_MODEL

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            if progress_cb:
                progress_cb(f"Downloading/loading {spec['label']}...", 0.1)

            load_kwargs: Dict[str, Any] = {"torch_dtype": dtype}
            if device == "cuda":
                load_kwargs["variant"] = "fp16"

            if spec["turbo"]:
                pipe = AutoPipelineForText2Image.from_pretrained(
                    spec["repo_id"], **load_kwargs
                )
            else:
                pipe = StableDiffusionPipeline.from_pretrained(
                    spec["repo_id"],
                    safety_checker=None,   # local desktop tool; saves ~1.2GB VRAM
                    requires_safety_checker=False,
                    **load_kwargs,
                )

            if progress_cb:
                progress_cb("Moving model to compute device...", 0.5)

            pipe = pipe.to(device)

            if device == "cuda":
                try:
                    pipe.enable_attention_slicing()
                    pipe.enable_vae_slicing()
                except Exception:
                    pass
            else:
                # CPU: keep memory footprint small
                try:
                    pipe.enable_attention_slicing()
                except Exception:
                    pass

            self.unload()
            self._pipe = pipe
            self._loaded_model_key = model_key
            self._device = device

            if progress_cb:
                progress_cb("Image model ready", 1.0)
            return device

    def unload(self) -> None:
        """Free VRAM/RAM held by the pipeline."""
        if self._pipe is not None:
            try:
                import torch
                del self._pipe
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            self._pipe = None
            self._loaded_model_key = None
            self._device = None
            gc.collect()

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        model_key: str = DEFAULT_MODEL,
        steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        seed: Optional[int] = None,
        width: int = 512,
        height: int = 512,
        optimize_for_3d: bool = True,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> Dict[str, Any]:
        """Generate an image from a prompt. Returns dict with PIL image + meta."""
        if not prompt or not prompt.strip():
            return {"success": False, "error": "Prompt is empty."}

        t_start = time.time()
        try:
            device = self.load(model_key, progress_cb=progress_cb)
        except Exception as exc:
            self._last_error = str(exc)
            return {"success": False, "error": f"Failed to load image model: {exc}"}

        spec = T2I_MODELS[self._loaded_model_key]
        final_prompt = f"{prompt.strip()}{_3D_QUALITY_SUFFIX}" if optimize_for_3d else prompt.strip()
        neg = negative_prompt.strip() or (_DEFAULT_NEGATIVE if not spec["turbo"] else "")

        n_steps = int(steps) if steps else spec["steps"]
        cfg = float(guidance_scale) if guidance_scale is not None else spec["guidance"]

        generator = None
        if seed is not None and int(seed) >= 0:
            import torch
            gen_device = "cuda" if device == "cuda" else "cpu"
            generator = torch.Generator(device=gen_device).manual_seed(int(seed))

        if progress_cb:
            progress_cb("Diffusing latent space...", 0.55)

        try:
            result = self._pipe(
                prompt=final_prompt,
                negative_prompt=neg or None,
                num_inference_steps=max(1, n_steps),
                guidance_scale=cfg,
                width=int(width),
                height=int(height),
                generator=generator,
            )
        except Exception as exc:
            return {"success": False, "error": f"Inference failed: {exc}"}

        image = result.images[0]
        elapsed = time.time() - t_start

        if progress_cb:
            progress_cb("Image generated", 1.0)

        return {
            "success": True,
            "image": image,
            "prompt_used": final_prompt,
            "model": self._loaded_model_key,
            "device": device,
            "steps": max(1, n_steps),
            "guidance_scale": cfg,
            "seed": seed,
            "elapsed_s": round(elapsed, 2),
        }

    def generate_variations(
        self,
        prompt: str,
        count: int = 3,
        base_seed: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate several seeds of the same prompt for quick A/B choice."""
        images = []
        errors = []
        base = int(base_seed) if base_seed is not None else int(time.time())
        for i in range(max(1, min(count, 6))):
            res = self.generate(prompt, seed=base + i * 7919, **kwargs)
            if res.get("success"):
                images.append(res["image"])
            else:
                errors.append(res.get("error"))
        return {"success": len(images) > 0, "images": images, "errors": errors}


def image_to_base64_data_url(pil_image, fmt: str = "PNG") -> str:
    """Encode a PIL image into a data URL usable by the frontend."""
    import base64
    import io

    buf = io.BytesIO()
    pil_image.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"