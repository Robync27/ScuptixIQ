import os
import sys
import warnings

# Suppress all noisy runtime warnings for a clean commercial desktop experience
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import base64
import gc
import io
import json
import shutil
import socket
import threading
import time
import traceback
import zipfile
from uuid import uuid4
from pathlib import Path
from typing import Any, Dict, List, Optional

import eel

# Multiprocessing support for Windows packaging
import multiprocessing
multiprocessing.freeze_support()

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# --- First-run AI dependency bootstrap (no-op when everything is bundled) ---
try:
    from bootstrap_deps import ensure_ai_deps
    if not ensure_ai_deps():
        print("[Setup] WARNING: AI components failed to install automatically.")
        print("[Setup] Run: pip install -r requirements.txt")
except Exception as _boot_err:  # never block startup because of the bootstrap
    print(f"[Setup] Bootstrap skipped: {_boot_err}")

from core import ImagePreprocessor, MeshProcessor, TSREngine, Text2ImageEngine

# --- Licensing (offline Pro/Studio keys) ------------------------------------
from core.license_manager import validate_license, save_license, load_saved_key
from core import hunyuan_multiview

@eel.expose
def get_license_status() -> Dict[str, Any]:
    """Current license tier for UI gating of Pro features."""
    return validate_license()

@eel.expose
def activate_license(key: str) -> Dict[str, Any]:
    """Activate a MESHF-XXXX-... key purchased from the seller."""
    ok = save_license(key)
    if not ok:
        return {"valid": False, "tier": "free", "reason": "invalid_key_format"}
    return validate_license()

_MODELS_DIR = str(_APP_DIR / "models")
_UI_DIR = str(_APP_DIR / "ui")
_OUTPUT_DIR = str(_APP_DIR / "ui" / "outputs")
_SAMPLES_DIR = str(_APP_DIR / "ui" / "samples")

os.makedirs(_MODELS_DIR, exist_ok=True)
os.makedirs(_OUTPUT_DIR, exist_ok=True)
os.makedirs(_SAMPLES_DIR, exist_ok=True)

# Initialize Eel UI directory at module level before any @eel.expose
eel.init(str(_UI_DIR))

# ---------------------------------------------------------------------------
# Single-instance socket lock
# ---------------------------------------------------------------------------
_LOCK_SOCKET = None
try:
    import socket
    _LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _LOCK_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _LOCK_SOCKET.bind(("127.0.0.1", 17860))
except socket.error:
    print("[WARNING] Another instance of MeshForge 3D may be running on port 17860.")

# ---------------------------------------------------------------------------
# Global engine state
# ---------------------------------------------------------------------------
_preprocessor: Optional[ImagePreprocessor] = None
_engine: Optional[TSREngine] = None
_processor: Optional[MeshProcessor] = None
_t2i_engine: Optional[Text2ImageEngine] = None
_last_generated_mesh: Optional[Any] = None
_last_bake_output: Optional[Dict[str, Any]] = None
_last_model_id: Optional[str] = None


def _get_preprocessor() -> ImagePreprocessor:
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = ImagePreprocessor()
    return _preprocessor


_engine_load_lock = threading.Lock()


def _get_engine() -> TSREngine:
    """Return the engine instance WITHOUT loading weights (cheap, non-blocking)."""
    global _engine
    with _engine_load_lock:
        if _engine is None:
            _engine = TSREngine(_MODELS_DIR)
    return _engine


def _load_engine_sync(target_device: str = "auto") -> TSREngine:
    """Load model weights (blocks until done; safe to call from any thread)."""
    global _engine
    with _engine_load_lock:
        if _engine is None:
            _engine = TSREngine(_MODELS_DIR)
        if not _engine.is_loaded:
            _engine.load(target_device)
    return _engine


def _preload_engine_background() -> None:
    """Start loading model weights in a daemon thread so the UI opens instantly."""
    def _worker():
        try:
            t0 = time.time()
            _load_engine_sync("auto")
            print(f"[Engine] Model ready in background in {time.time() - t0:.1f}s")
        except Exception as exc:
            print(f"[WARNING] Background model load failed (will retry on first generation): {exc}")

    threading.Thread(target=_worker, daemon=True).start()


def _get_processor() -> MeshProcessor:
    global _processor
    if _processor is None:
        _processor = MeshProcessor()
    return _processor


def _get_t2i_engine() -> Text2ImageEngine:
    global _t2i_engine
    if _t2i_engine is None:
        _t2i_engine = Text2ImageEngine()
    return _t2i_engine


# ===================================================================
# Eel Exposed API (Callable from JavaScript)
# ===================================================================

@eel.expose
def get_system_info() -> Dict[str, Any]:
    """Return hardware capabilities and model status for the frontend."""
    hw = TSREngine.get_hardware_info()
    engine = _get_engine()

    return {
        "hardware": hw,
        "active_device": engine.active_device if engine and engine.is_loaded else hw["best_device"],
        "model_loaded": engine.is_loaded if engine else False,
        "app_version": "2.0.0",
    }


@eel.expose
def set_device(device_name: str) -> Dict[str, Any]:
    """Switch execution device (e.g. 'cuda:0' or 'cpu')."""
    engine = _get_engine()
    try:
        engine.set_device(device_name)
        return {"success": True, "active_device": engine.active_device}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@eel.expose
def get_sample_images() -> List[Dict[str, str]]:
    """Return available sample images for 1-click test."""
    samples = []
    if os.path.isdir(_SAMPLES_DIR):
        for fname in sorted(os.listdir(_SAMPLES_DIR)):
            if fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                name = os.path.splitext(fname)[0].replace("_", " ").title()
                samples.append({
                    "id": fname,
                    "name": name,
                    "url": f"/samples/{fname}",
                })
    return samples


@eel.expose
def check_assets() -> Dict[str, Any]:
    """Check if model checkpoint is downloaded and ready."""
    config_path = os.path.join(_MODELS_DIR, "config.yaml")
    ckpt_path = os.path.join(_MODELS_DIR, "model.ckpt")
    ready = os.path.isfile(config_path) and os.path.isfile(ckpt_path)
    return {"ready": ready}


@eel.expose
def generate_3d(image_base64: str, options_json: str = "{}") -> Dict[str, Any]:
    """Main image-to-3D generation pipeline.
    
    Args:
        image_base64: Base64 data URL or raw base64 string
        options_json: JSON string with generation options:
            - resolution: int (128, 256, 384)
            - bake_texture: bool
            - texture_resolution: int (512, 1024, 2048)
            - remove_bg: bool
            - foreground_ratio: float (0.6 - 0.95)
            - device: str ('auto', 'cuda:0', 'cpu')
    """
    global _last_generated_mesh, _last_bake_output, _last_model_id

    try:
        options = json.loads(options_json) if isinstance(options_json, str) else (options_json or {})
    except Exception:
        options = {}

    resolution = int(options.get("resolution", 256))
    bake_texture = bool(options.get("bake_texture", True))
    texture_mode = str(options.get("texture_mode", "uv_atlas" if bake_texture else "vertex_colors"))
    texture_resolution = int(options.get("texture_resolution", 1024))
    remove_bg = bool(options.get("remove_bg", True))
    foreground_ratio = float(options.get("foreground_ratio", 0.85))
    target_device = options.get("device", "auto")

    # --- Free tier limits: mesh only, no baked texture, medium quality ------
    lic = validate_license()
    free_tier = (not lic.get("valid")) or lic.get("tier") == "free"
    tier_notice = None
    if free_tier:
        resolution = min(resolution, 256)
        bake_texture = False
        texture_mode = "none"
        texture_resolution = min(texture_resolution, 512)
        tier_notice = ("Free edition: pure mesh without colors or textures, medium quality. "
                       "Activate a Pro license for vertex colors and 8K textured models.")

    try:
        # Step 1: Decode image
        try:
            eel.updateProgress("Decoding image...", 0.05)()
        except Exception:
            pass

        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
        image_bytes = base64.b64decode(image_base64)
        pil_image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(image_bytes))

        # Step 2: Preprocess image
        try:
            eel.updateProgress("Removing background & centering...", 0.15)()
        except Exception:
            pass

        preprocessor = _get_preprocessor()
        model_input, preview_rgba = preprocessor.process_for_model(
            pil_image,
            foreground_ratio=foreground_ratio,
            remove_bg=remove_bg,
        )

        # Save preprocessed preview
        timestamp = int(time.time() * 1000)
        model_id = f"model_{timestamp}"
        preview_path = os.path.join(_OUTPUT_DIR, f"{model_id}_preview.png")
        preview_rgba.save(preview_path)

        # Step 3: Run 3D Neural Engine (loads on demand if background preload
        # has not finished yet — the lock makes this wait safely)
        try:
            eel.updateProgress("Preparing neural engine...", 0.25)()
        except Exception:
            pass
        engine = _load_engine_sync(target_device)
        if target_device != "auto" and engine.active_device != target_device:
            engine.set_device(target_device)

        def _progress_bridge(phase: str, pct: float):
            try:
                eel.updateProgress(phase, pct)()
            except Exception:
                pass

        mesh, bake_output, elapsed = engine.generate(
            model_input,
            resolution=resolution,
            texture_mode=texture_mode,
            bake_uv_texture=(texture_mode == "uv_atlas"),
            texture_resolution=texture_resolution,
            progress_cb=_progress_bridge,
        )

        processor = _get_processor()
        _last_generated_mesh = mesh
        _last_bake_output = bake_output
        _last_model_id = model_id

        # Step 4: Export primary GLB
        try:
            eel.updateProgress("Exporting 3D GLB file...", 0.90)()
        except Exception:
            pass

        glb_filename = f"{model_id}.glb"
        glb_path = os.path.join(_OUTPUT_DIR, glb_filename)
        processor.export_glb(mesh, glb_path, bake_output=bake_output)

        stats = processor.get_mesh_stats(mesh)
        stats["generation_time_s"] = round(elapsed, 2)
        stats["device_used"] = engine.active_device
        stats["resolution"] = resolution
        stats["has_baked_texture"] = bake_texture and (bake_output is not None)

        result = {
            "success": True,
            "model_id": model_id,
            "model_url": f"/outputs/{glb_filename}",
            "preview_url": f"/outputs/{model_id}_preview.png",
            "stats": stats,
            "tier": lic.get("tier", "free"),
        }
        if tier_notice:
            result["notice"] = tier_notice
        return result

    except Exception as exc:
        traceback.print_exc()
        return {
            "success": False,
            "error": str(exc),
        }


@eel.expose
def generate_multiview(views: Dict[str, str], options_json: str = "{}") -> Dict[str, Any]:
    """Generate a single mesh from labeled front and supporting views."""
    global _last_generated_mesh, _last_bake_output, _last_model_id

    try:
        if not isinstance(views, dict) or not views.get("front") or len(views) < 2:
            raise ValueError("Choose a front image and at least one back, left, or right image.")
        if set(views) - set(hunyuan_multiview.VIEWS):
            raise ValueError("Supported views are front, back, left, and right.")

        options = json.loads(options_json)
        resolution = int(options.get("resolution", 256))
        if resolution not in (128, 256, 384, 512):
            raise ValueError("Choose a supported geometry resolution.")
        lic = validate_license()
        if not lic.get("valid") or lic.get("tier") == "free":
            resolution = min(resolution, 256)

        device = options.get("device", "auto")
        if device in ("auto", "best"):
            device = "cuda:0"
        if not isinstance(device, str) or not device.startswith("cuda:") or not device[5:].isdigit():
            raise ValueError("Select Auto or an NVIDIA CUDA device for Multi-Image mode.")

        runtime = hunyuan_multiview.runtime_paths()
        # Release the background-preloaded TripoSR model before starting CUDA inference.
        with _engine_load_lock:
            if _engine is not None and _engine.is_loaded:
                _engine.unload()

        start = time.monotonic()
        try:
            eel.updateProgress("Running Hunyuan3D-2mv (first run downloads weights)...", 0.25)()
        except Exception:
            pass
        mesh = hunyuan_multiview.generate_mesh(
            views, resolution, bool(options.get("remove_bg", True)), device, runtime,
        )

        processor = _get_processor()
        model_id = f"model_{uuid4().hex}"
        filename = f"{model_id}.glb"
        stats = processor.get_mesh_stats(mesh)
        stats.update(
            generation_time_s=round(time.monotonic() - start, 2),
            device_used=device, resolution=resolution, has_baked_texture=False,
        )
        processor.export_glb(mesh, os.path.join(_OUTPUT_DIR, filename))
        _last_generated_mesh, _last_bake_output, _last_model_id = mesh, None, model_id

        return {
            "success": True, "model_id": model_id,
            "model_url": f"/outputs/{filename}", "stats": stats,
            "tier": lic.get("tier", "free"),
        }
    except Exception as exc:
        traceback.print_exc()
        return {"success": False, "error": str(exc)}


# ===================================================================
# Batch Processing (folder of images -> folder of GLB files)
# ===================================================================

_BATCH_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


@eel.expose
def generate_batch(input_dir: str, output_dir: str, options_json: str = "{}") -> Dict[str, Any]:
    """Batch mode: convert every image in `input_dir` into a GLB in `output_dir`.

    Options are the same as for `generate_3d` (resolution, remove_bg, ...).
    Free-tier limits are applied per image, exactly like single generation.
    """
    try:
        options = json.loads(options_json) if isinstance(options_json, str) else (options_json or {})
    except Exception:
        options = {}

    if not input_dir or not os.path.isdir(input_dir):
        return {"success": False, "error": f"Input folder not found: {input_dir}", "results": []}

    files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith(_BATCH_IMAGE_EXTS)
    )
    if not files:
        return {"success": False, "error": "No images found in the input folder.", "results": []}

    os.makedirs(output_dir, exist_ok=True)

    resolution = int(options.get("resolution", 256))
    bake_texture = bool(options.get("bake_texture", True))
    texture_mode = str(options.get("texture_mode", "uv_atlas" if bake_texture else "vertex_colors"))
    texture_resolution = int(options.get("texture_resolution", 1024))
    remove_bg = bool(options.get("remove_bg", True))
    foreground_ratio = float(options.get("foreground_ratio", 0.85))
    target_device = options.get("device", "auto")

    # Free tier limits (same policy as single generation)
    lic = validate_license()
    free_tier = (not lic.get("valid")) or lic.get("tier") == "free"
    if free_tier:
        resolution = min(resolution, 256)
        bake_texture = False
        texture_mode = "none"
        texture_resolution = min(texture_resolution, 512)

    preprocessor = _get_preprocessor()
    processor = _get_processor()
    results: List[Dict[str, Any]] = []
    ok_count = 0

    for idx, fname in enumerate(files):
        base = os.path.splitext(fname)[0]
        item: Dict[str, Any] = {"file": fname}
        try:
            try:
                eel.updateProgress(f"Batch {idx + 1}/{len(files)}: {fname}", idx / len(files))()
            except Exception:
                pass

            pil_image = __import__("PIL.Image", fromlist=["Image"]).open(
                os.path.join(input_dir, fname)
            )
            model_input, _preview = preprocessor.process_for_model(
                pil_image,
                foreground_ratio=foreground_ratio,
                remove_bg=remove_bg,
            )

            engine = _load_engine_sync(target_device)
            if target_device != "auto" and engine.active_device != target_device:
                engine.set_device(target_device)

            mesh, bake_output, elapsed = engine.generate(
                model_input,
                resolution=resolution,
                texture_mode=texture_mode,
                bake_uv_texture=(texture_mode == "uv_atlas"),
                texture_resolution=texture_resolution,
            )

            glb_path = os.path.join(output_dir, f"{base}.glb")
            processor.export_glb(mesh, glb_path, bake_output=bake_output)

            item.update({
                "success": True,
                "glb": glb_path,
                "time_s": round(elapsed, 2),
                "vertices": processor.get_mesh_stats(mesh).get("vertex_count"),
            })
            ok_count += 1
        except Exception as exc:
            traceback.print_exc()
            item.update({"success": False, "error": str(exc)})

        results.append(item)

    summary = {
        "success": True,
        "total": len(files),
        "ok": ok_count,
        "failed": len(files) - ok_count,
        "output_dir": output_dir,
        "results": results,
        "tier": lic.get("tier", "free"),
    }
    if free_tier:
        summary["notice"] = ("Free edition: batch produced pure meshes without colors or textures. "
                             "Activate a Pro license for textured models.")
    try:
        eel.updateProgress(f"Batch complete: {ok_count}/{len(files)} models", 1.0)()
    except Exception:
        pass
    return summary


# ===================================================================
# Text-to-Image (Open-Source Prompt → Concept Image → 3D)
# ===================================================================

@eel.expose
def get_t2i_models() -> Dict[str, Any]:
    """List available open-source text-to-image models and install status."""
    return {
        "models": [
            {"key": key, **{k: v for k, v in spec.items()}}
            for key, spec in Text2ImageEngine.list_models().items()
        ],
        "default": "dreamshaper",
        "diffusers_installed": Text2ImageEngine.check_diffusers_installed(),
        "hardware": Text2ImageEngine.get_hardware_info(),
    }


@eel.expose
def generate_image_from_prompt(prompt: str, options_json: str = "{}") -> Dict[str, Any]:
    """Generate a concept image from a text prompt using open-source models.

    The result can be sent straight into `generate_3d` (prompt-to-3D pipeline).

    Options:
        - model: str ('dreamshaper', 'sd15', 'sd-turbo', 'sdxl-turbo')
        - negative_prompt: str
        - steps: int
        - guidance_scale: float
        - seed: int (-1 = random)
        - optimize_for_3d: bool (append 3D-friendly quality suffix)
    """
    try:
        options = json.loads(options_json) if isinstance(options_json, str) else (options_json or {})
    except Exception:
        options = {}

    model_key = str(options.get("model", "dreamshaper"))
    negative_prompt = str(options.get("negative_prompt", ""))
    steps = options.get("steps")
    guidance_scale = options.get("guidance_scale")
    seed = options.get("seed", -1)
    if seed is None or int(seed) < 0:
        seed = int(time.time()) % (2 ** 31)
    optimize_for_3d = bool(options.get("optimize_for_3d", True))

    def _progress_bridge(phase: str, pct: float):
        try:
            eel.updateProgress(phase, pct * 0.9)()
        except Exception:
            pass

    engine = _get_t2i_engine()
    result = engine.generate(
        prompt=prompt,
        negative_prompt=negative_prompt,
        model_key=model_key,
        steps=steps,
        guidance_scale=guidance_scale,
        seed=int(seed),
        width=int(options.get("width", 512)),
        height=int(options.get("height", 512)),
        optimize_for_3d=optimize_for_3d,
        progress_cb=_progress_bridge,
    )

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Unknown error")}

    # Persist to outputs dir so it can be reused as a source image later
    timestamp = int(time.time() * 1000)
    image_id = f"t2i_{timestamp}"
    image_path = os.path.join(_OUTPUT_DIR, f"{image_id}.png")
    try:
        result["image"].save(image_path)
    except Exception:
        pass

    from core.text2image_engine import image_to_base64_data_url

    try:
        eel.updateProgress("Completed successfully!", 1.0)()
    except Exception:
        pass

    return {
        "success": True,
        "image_id": image_id,
        "image_data_url": image_to_base64_data_url(result["image"]),
        "image_url": f"/outputs/{image_id}.png",
        "prompt_used": result["prompt_used"],
        "model": result["model"],
        "device": result["device"],
        "seed": result["seed"],
        "elapsed_s": result["elapsed_s"],
    }


@eel.expose
def unload_image_model() -> Dict[str, Any]:
    """Free RAM/VRAM used by the text-to-image pipeline."""
    if _t2i_engine is not None:
        _t2i_engine.unload()
    return {"success": True}


@eel.expose
def export_model_format(model_id: str, fmt: str) -> Dict[str, Any]:
    """Export current 3D model into requested format (.glb, .obj, .stl, .ply)."""
    global _last_generated_mesh, _last_bake_output

    if _last_generated_mesh is None:
        return {"success": False, "error": "No mesh available in memory to export."}

    processor = _get_processor()
    fmt = fmt.lower().strip(".")

    try:
        if fmt == "glb":
            path = os.path.join(_OUTPUT_DIR, f"{model_id}.glb")
            if not os.path.isfile(path):
                processor.export_glb(_last_generated_mesh, path, bake_output=_last_bake_output)
            return {"success": True, "download_url": f"/outputs/{model_id}.glb", "filename": f"{model_id}.glb"}

        elif fmt == "stl":
            path = os.path.join(_OUTPUT_DIR, f"{model_id}.stl")
            processor.export_stl(_last_generated_mesh, path)
            return {"success": True, "download_url": f"/outputs/{model_id}.stl", "filename": f"{model_id}.stl"}

        elif fmt == "ply":
            path = os.path.join(_OUTPUT_DIR, f"{model_id}.ply")
            processor.export_ply(_last_generated_mesh, path)
            return {"success": True, "download_url": f"/outputs/{model_id}.ply", "filename": f"{model_id}.ply"}

        elif fmt == "obj":
            obj_path = os.path.join(_OUTPUT_DIR, f"{model_id}.obj")
            processor.export_obj(_last_generated_mesh, obj_path, bake_output=_last_bake_output)

            # If baked texture exists, bundle into ZIP
            tex_path = os.path.join(_OUTPUT_DIR, f"{model_id}.png")
            if os.path.isfile(tex_path):
                zip_path = os.path.join(_OUTPUT_DIR, f"{model_id}_obj.zip")
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(obj_path, arcname=f"{model_id}.obj")
                    zf.write(tex_path, arcname=f"{model_id}.png")
                return {"success": True, "download_url": f"/outputs/{model_id}_obj.zip", "filename": f"{model_id}_obj.zip"}
            else:
                return {"success": True, "download_url": f"/outputs/{model_id}.obj", "filename": f"{model_id}.obj"}

        else:
            return {"success": False, "error": f"Unsupported format '{fmt}'"}

    except Exception as exc:
        traceback.print_exc()
        return {"success": False, "error": str(exc)}


# ===================================================================
# Server Startup
# ===================================================================

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_available_port(preferred_port: int = 7860) -> int:
    for port in range(preferred_port, preferred_port + 20):
        if not is_port_in_use(port):
            return port
    return preferred_port


def start_app() -> None:
    """Launch the Eel application with the modern MeshForge 3D web UI."""
    import argparse
    import subprocess
    import urllib.request
    import webbrowser

    parser = argparse.ArgumentParser(description="MeshForge 3D Universal Studio")
    parser.add_argument("--port", type=int, default=7860, help="Port to bind to")
    parser.add_argument("--host", type=str, default="localhost", help="Host address")
    parser.add_argument("--window", action="store_true", help="Launch in native desktop app window")
    parser.add_argument("--browser", action="store_true", help="Open default web browser")
    parser.add_argument("--no-browser", action="store_true", help="Do not open any browser window")
    parser.add_argument("--no-tray", action="store_true", help="Disable system tray icon")
    args, _ = parser.parse_known_args()

    launch_mode = None
    if args.window:
        launch_mode = "chrome"  # Falls back to Edge or default browser
    elif args.browser:
        launch_mode = "default"
    elif args.no_browser:
        launch_mode = None
    else:
        launch_mode = "default"

    target_port = args.port

    # If port is already in use, check if it's our running server and open directly
    if is_port_in_use(target_port):
        try:
            req = urllib.request.Request(f"http://localhost:{target_port}/", headers={"User-Agent": "MeshForge"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    print(f"[Info] MeshForge 3D is already active at http://localhost:{target_port}. Bringing up window...")
                    opened = False
                    if args.window:
                        for browser_cmd in [
                            [r"C:\Program Files\Google\Chrome\Application\chrome.exe", f"--app=http://localhost:{target_port}"],
                            [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", f"--app=http://localhost:{target_port}"],
                            [r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", f"--app=http://localhost:{target_port}"],
                        ]:
                            try:
                                subprocess.Popen(browser_cmd)
                                opened = True
                                break
                            except Exception:
                                pass
                    if not opened and not args.no_browser:
                        webbrowser.open(f"http://localhost:{target_port}")
                    return
        except Exception:
            target_port = find_available_port(target_port)

    print("=" * 60)
    print("  MeshForge 3D — Universal 3D Reconstruction Studio")
    print("=" * 60)

    hw = TSREngine.get_hardware_info()
    print(f"[Hardware] GPU: {hw['cuda_devices'][0]['name'] if hw['has_cuda'] else 'None detected'}")
    print(f"[Hardware] CPU: {hw['cpu_info']}")
    print(f"[Hardware] Selected backend: {hw['best_device'].upper()}")

    # Preload engine in background — the window opens instantly, weights
    # finish loading while the user picks an image
    print("[Engine] Loading model in background...")
    _preload_engine_background()

    target_port = find_available_port(args.port)
    print(f"[Server] MeshForge 3D server starting at http://localhost:{target_port}")

    try:
        eel.start(
            "index.html",
            mode=launch_mode,
            host="localhost",
            port=target_port,
            size=(1440, 920),
            suppress_error=True,
            block=False,
        )
    except Exception as exc:
        print(f"[Warning] Server startup notice: {exc}")

    print("[Ready] Application is ready for 3D generation.")

    # --- System tray: closing the window keeps the app alive in the tray ----
    tray = None
    if not args.no_tray and os.name == "nt":
        try:
            from tray import TrayIcon

            def _quit_from_tray():
                print("[Shutdown] Quit requested from tray...")
                if _engine is not None:
                    _engine.unload()
                if _t2i_engine is not None:
                    _t2i_engine.unload()
                if _LOCK_SOCKET is not None:
                    _LOCK_SOCKET.close()
                os._exit(0)

            tray = TrayIcon(f"http://localhost:{target_port}", on_quit=_quit_from_tray)
            tray.start()
        except Exception as exc:
            print(f"[Tray] Disabled: {exc}")

    try:
        while True:
            eel.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Shutdown] Stopping MeshForge 3D...")
        if _engine is not None:
            _engine.unload()
        if _LOCK_SOCKET is not None:
            _LOCK_SOCKET.close()
        sys.exit(0)


if __name__ == "__main__":
    start_app()