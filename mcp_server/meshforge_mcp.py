"""
MeshForge 3D — MCP Server (Model Context Protocol over stdio)
==============================================================
Lets AI agents (Claude Desktop, Cline, Cursor, any MCP client) generate
3D models from images or text prompts using the local MeshForge engine.

Tools exposed:
    get_status()                  -> hardware, license tier, model readiness
    generate_model(image_path, resolution) -> GLB file path + stats
    text_to_3d(prompt, model_key) -> image generated via open-source SD,
                                     then reconstructed into a GLB mesh

Client configuration example (Claude Desktop / Cline / Cursor):
{
  "mcpServers": {
    "meshforge3d": {
      "command": "python",
      "args": ["C:/3dmodel_app/MeshForge3D/mcp_server/meshforge_mcp.py"]
    }
  }
}

Protocol: JSON-RPC 2.0 over stdio (MCP spec), zero external dependencies.
"""

import base64
import io
import json
import os
import sys
import time
from pathlib import Path

# --- Make the application package importable --------------------------------
APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from core import ImagePreprocessor, MeshProcessor, TSREngine, Text2ImageEngine
from core.license_manager import validate_license

MODELS_DIR = str(APP_DIR / "models")
OUTPUT_DIR = APP_DIR / "ui" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_engine = None
_processor = None
_preprocessor = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = TSREngine(MODELS_DIR)
        _engine.load("auto")
    return _engine


def get_processor():
    global _processor
    if _processor is None:
        _processor = MeshProcessor()
    return _processor


def get_preprocessor():
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = ImagePreprocessor()
    return _preprocessor


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def tool_get_status() -> dict:
    hw = TSREngine.get_hardware_info()
    lic = validate_license()
    ckpt = os.path.join(MODELS_DIR, "model.ckpt")
    return {
        "gpu": hw["cuda_devices"][0]["name"] if hw["has_cuda"] else "none",
        "best_device": hw["best_device"],
        "license_tier": lic.get("tier"),
        "license_valid": lic.get("valid"),
        "model_downloaded": os.path.isfile(ckpt),
        "outputs_dir": str(OUTPUT_DIR),
    }


def tool_generate_model(image_path: str, resolution: int = 256) -> dict:
    """Image file -> preprocessed -> TripoSR -> GLB on disk."""
    from PIL import Image as PILImage

    p = Path(image_path)
    if not p.is_file():
        return {"success": False, "error": f"File not found: {image_path}"}

    # Free tier limits (same policy as the GUI)
    lic = validate_license()
    free_tier = (not lic.get("valid")) or lic.get("tier") == "free"
    if free_tier:
        resolution = min(resolution, 256)
        texture_mode = "vertex_colors"
    else:
        texture_mode = "uv_atlas"

    img = PILImage.open(p).convert("RGB")
    model_input, _preview = get_preprocessor().process_for_model(
        img, foreground_ratio=0.85, remove_bg=True
    )

    engine = get_engine()
    mesh, bake_output, elapsed = engine.generate(
        model_input,
        resolution=resolution,
        texture_mode=texture_mode,
        bake_uv_texture=(texture_mode == "uv_atlas"),
        texture_resolution=1024,
    )

    out = OUTPUT_DIR / f"mcp_{int(time.time() * 1000)}.glb"
    get_processor().export_glb(mesh, str(out), bake_output=bake_output)
    stats = get_processor().get_mesh_stats(mesh)
    stats["generation_time_s"] = round(elapsed, 2)
    return {"success": True, "glb_path": str(out), "tier": lic.get("tier"), "stats": stats}


def tool_text_to_3d(prompt: str, model_key: str = "dreamshaper",
                    steps: int = None, seed: int = -1) -> dict:
    """Prompt -> concept image (open-source SD) -> GLB mesh."""
    t2i = Text2ImageEngine()
    res = t2i.generate(
        prompt=prompt, negative_prompt="", model_key=model_key,
        steps=steps, guidance_scale=None, seed=int(seed),
        width=512, height=512, optimize_for_3d=True,
    )
    if not res.get("success"):
        return {"success": False, "error": res.get("error")}

    img_path = OUTPUT_DIR / f"mcp_t2i_{int(time.time() * 1000)}.png"
    res["image"].save(img_path)
    result = tool_generate_model(str(img_path), resolution=256)
    result["source_image"] = str(img_path)
    result["prompt_used"] = res.get("prompt_used")
    return result


# ---------------------------------------------------------------------------
# MCP protocol plumbing (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_status",
        "description": "Get MeshForge 3D status: GPU, license tier, whether the TripoSR model is downloaded.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_model",
        "description": "Generate a 3D model (GLB) from an image file. Returns the path to the .glb file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Absolute or relative path to a PNG/JPG image"},
                "resolution": {"type": "integer", "description": "Grid resolution 128/256/384 (free tier caps at 256)", "default": 256},
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "text_to_3d",
        "description": "Generate a concept image from a text prompt with an open-source Stable Diffusion model, then reconstruct it into a 3D GLB mesh. Returns paths to both the image and the .glb.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Text description of the object"},
                "model_key": {"type": "string", "enum": ["dreamshaper", "sd15", "sd-turbo", "sdxl-turbo"], "default": "dreamshaper"},
                "steps": {"type": "integer", "description": "Diffusion steps (optional)"},
                "seed": {"type": "integer", "description": "Random seed (-1 = random)", "default": -1},
            },
            "required": ["prompt"],
        },
    },
]


def dispatch(name: str, arguments: dict) -> dict:
    if name == "get_status":
        return tool_get_status()
    if name == "generate_model":
        return tool_generate_model(arguments["image_path"],
                                   int(arguments.get("resolution", 256)))
    if name == "text_to_3d":
        return tool_text_to_3d(arguments["prompt"],
                               arguments.get("model_key", "dreamshaper"),
                               arguments.get("steps"),
                               int(arguments.get("seed", -1)))
    raise ValueError(f"Unknown tool: {name}")


def handle(msg: dict) -> dict:
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "meshforge3d", "version": "2.1.0"},
        }}
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        try:
            data = dispatch(params["name"], params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}],
                "isError": not data.get("success", True),
            }}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            }}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Unknown method: {method}"}}
    return None


def main() -> None:
    print("[MeshForge MCP] Server started on stdio.", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + chr(10))
            sys.stdout.flush()


if __name__ == "__main__":
    main()