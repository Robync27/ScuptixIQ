# 🔥 MeshForge 3D — Universal 3D Reconstruction Studio

![License](https://img.shields.io/badge/license-MIT-green) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-yellow) ![GPU](https://img.shields.io/badge/CUDA%20%7C%20CPU-supported-brightgreen) ![Offline](https://img.shields.io/badge/100%25-offline-orange) ![Stars](https://img.shields.io/badge/%E2%AD%90-star%20if%20useful-ffcc00)

> **From idea to 3D model in 60 seconds — fully offline, no subscriptions, no limits, no watermarks.**

MeshForge 3D turns a single photo (or a text prompt) into a ready-to-use 3D mesh.
Powered by the open-source **TripoSR** engine (Tripo AI + Stability AI, MIT) —
everything runs **100% locally**: nothing ever leaves your computer.

![MeshForge 3D](docs/screenshot.png)

## 🆚 Why not Meshy / Tripo AI / Luma?

| | Cloud services (Meshy, Tripo…) | **MeshForge 3D** |
|---|---|---|
| Privacy | Your photos go to their servers | **Nothing leaves your PC** |
| Pricing | Subscription + credit limits | **Free core, one-time Pro key** |
| Internet | Required | **Not needed after setup** |
| Limits | Credits run out | **Unlimited generations** |
| Watermarks | On free plans | **None, ever** |

## 🎯 Who is it for

- 🖨️ **3D-print hobbyists** — STL from a photo in a minute
- 🎮 **Indie game devs** — props & assets for Unity / Godot / Unreal
- 🛒 **Marketplace sellers** — 3D visuals of products
- 🏠 **Architects & interior designers** — fast furniture concepts
- 🎓 **Education** — a friendly entry into 3D + AI
- 🤖 **AI-agent builders** — MCP server for Claude Desktop / Cline / Cursor


---

## ✨ Features

- 🖼️ **Image → 3D** — single photo to watertight mesh (GLB / OBJ / STL / PLY)
- ✍️ **Prompt → 3D** — built-in open-source text-to-image (DreamShaper, SD 1.5, SD-Turbo),
  the concept image feeds straight into 3D reconstruction
- 🧠 **TripoSR neural engine** — vendored, MIT-licensed, no cloud calls
- ✂️ **AI background removal** (rembg / u2net) — messy photos work fine
- 🎮 **Live 3D preview** — Three.js viewer right in the app
- 💻 **CUDA / CPU** — auto-detects your hardware
- 🖥️ **Desktop app** — Eel + Chrome/Edge app window, system tray, instant startup
- 🤖 **MCP server** — connect AI agents (Claude Desktop, Cline, Cursor) to generate 3D models
- 🐳 **Docker** support

## 💰 Free vs Pro

| | **Free (this repo, MIT)** | **Pro / Studio** |
|---|---|---|
| Image → 3D mesh | ✅ | ✅ |
| Export GLB / OBJ / STL / PLY | ✅ | ✅ |
| Mesh quality | **Medium (≤256 grid)** | High (up to 384 grid) |
| Textures | **None — pure geometry, no colors** | Vertex colors + UV atlas, baked up to **8K** |
| Batch mode (folder → folder) | — | ✅ |
| Text-to-Image concept generator | — | ✅ |
| Commercial usage rights (company) | — | ✅ Studio |
| Priority support | — | ✅ |

The Free tier is **not crippled by watermarks or time limits** — you get a clean,
watermark-free mesh forever. Pro unlocks textures, higher resolution and batch tools.

**Upgrade to Pro** → [pricing page / Gumroad link] · License keys activate **offline**
in one click (`Menu → Activate License`).

## 🚀 Quick Start

### Requirements
- Windows 10/11 (Linux/macOS work from source), Python 3.10–3.12
- NVIDIA GPU with ≥6 GB VRAM recommended (CPU works, slower)

### From source

```bash
git clone https://github.com/YOUR_USERNAME/MeshForge3D.git
cd MeshForge3D
pip install -r requirements.txt
cd app
python main.py --window
```

On first launch the app downloads the TripoSR checkpoint (~700 MB) into `app/models/`
automatically. After that it works **fully offline**.

### Docker

```bash
docker build -t meshforge3d .
docker run -p 7860:7860 meshforge3d
# open http://localhost:7860
```

## 🤖 MCP server (for AI agents)

Expose MeshForge 3D to Claude Desktop / Cline / Cursor:

```json
{
  "mcpServers": {
    "meshforge3d": {
      "command": "python",
      "args": ["C:/path/to/MeshForge3D/mcp_server/meshforge_mcp.py"]
    }
  }
}
```

Tools: `get_status`, `generate_model(image_path, resolution)`, `text_to_3d(prompt)`.
Free-tier limits apply the same way as in the GUI.

## 📦 Building installers (optional)

```bash
python tools/build_lite.py     # Lite web-installer (~46 MB, downloads AI deps on first run)
python build_installer.py      # Full offline installer
```

## 🧩 Project structure

```
MeshForge3D/
├── app/
│   ├── main.py               # Eel app: generation API, Free/Pro gating, batch
│   ├── core/
│   │   ├── license_manager.py  # offline HMAC license keys (Free/Pro/Studio)
│   │   ├── text2image_engine.py# open-source prompt→image engine
│   │   ├── mesh_processor.py   # export GLB/OBJ/STL/PLY, UV baking
│   │   └── image_preprocessor.py# rembg background removal
│   ├── ui/                   # Three.js web UI
│   ├── downloader.py         # first-run model download
│   └── tray.py               # system tray icon
├── tsr_sdk/                  # vendored TripoSR (MIT)
├── mcp_server/               # MCP server for AI agents (zero deps)
├── tools/                    # build, VirusTotal check, MCP tests
└── installer*.iss            # Inno Setup scripts
```

## 🔑 License key CLI (for sellers)

```bash
cd app
python -m core.license_manager gen pro 202712     # Pro key, expires 2027-12
python -m core.license_manager gen studio 0       # perpetual Studio key
python -m core.license_manager check-saved        # validate local activation
```

Sell keys via Gumroad / Lemon Squeezy / itch.io — validation is fully offline.

## ⚖️ Licenses & credits

- **MeshForge 3D core** — MIT (see [LICENSE](LICENSE))
- **TripoSR** — MIT © Tripo AI & Stability AI ([tsr_sdk](tsr_sdk))
- **rembg, xatlas, trimesh, diffusers** — MIT/Apache (see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md))
- Model weights (TripoSR checkpoint, Stable Diffusion) are **not distributed** in this
  repo — they are downloaded by the app at first run under their own model licenses.

## ⭐ Support the project

If MeshForge 3D saves you time, please **star the repo** and **share your renders** —
it directly helps the project. Buying a Pro license funds new features
(multi-view reconstruction, texture upscaling, Blender/Unity export plugins).

## ❓ FAQ

**Does the free version expire or add watermarks?**
No. The Free tier is unlimited and watermark-free forever — meshes are pure
geometry (clay), without colors or textures.

**Do I need a GPU?**
No, CPU works (slower). NVIDIA GPU with 6+ GB VRAM is recommended (~6 s per model).

**Does it send my images anywhere?**
Never. Generation is 100% local; the only network use is the one-time model download.

**Can I sell models I generate?**
Yes — Free tier output is yours. For company-wide commercial deployment, get a
Studio license.

**Is there an API?**
Yes — the built-in MCP server lets AI agents (Claude Desktop, Cline, Cursor)
generate models with a tool call.

## 🗺️ Roadmap

- [x] Image → 3D (TripoSR)
- [x] Prompt → Image → 3D pipeline
- [x] Batch processing
- [x] MCP server for AI agents
- [ ] Multi-view reconstruction (4 views → better geometry)
- [ ] Real-ESRGAN texture upscaling
- [ ] One-click send to Blender / Unity / Unreal
