# Third-Party Licenses

MeshForge 3D builds on the following open-source components. All model weights are
downloaded by the application at first run and are **not distributed** with this
repository or its installers.

## Code components

| Component | License | Source | Used for |
|---|---|---|---|
| TripoSR (`tsr_sdk/`) | MIT | https://github.com/VAST-AI-Research/TripoSR | Image-to-3D neural reconstruction engine |
| Eel | MIT | https://github.com/python-eel/Eel | Desktop app framework (Python + web UI) |
| Three.js | MIT | https://github.com/mrdoob/three.js | In-app 3D viewer |
| rembg | MIT | https://github.com/danielgatis/rembg | AI background removal |
| trimesh | MIT | https://github.com/mikedh/trimesh | Mesh processing & export |
| PyMCubes | MIT | https://github.com/pmneila/PyMCubes | Marching cubes isosurfacing |
| scikit-image | BSD-3-Clause | https://github.com/scikit-image/scikit-image | Image / mesh utilities |
| SciPy | BSD-3-Clause | https://github.com/scipy/scipy | Scientific utilities |
| xatlas | MIT | https://github.com/jpcy/xatlas | UV unwrapping |
| moderngl | MIT | https://github.com/moderngl/moderngl | GPU texture baking |
| NumPy | BSD-3-Clause | https://github.com/numpy/numpy | Core numerics |
| Pillow | MIT-CMU | https://github.com/python-pillow/Pillow | Image I/O |
| OpenCV (headless) | Apache-2.0 | https://github.com/opencv/opencv-python | Image processing |
| PyTorch | BSD-3-Clause | https://github.com/pytorch/pytorch | Deep learning runtime |
| Transformers | Apache-2.0 | https://github.com/huggingface/transformers | Model loading |
| diffusers | Apache-2.0 | https://github.com/huggingface/diffusers | Text-to-image pipeline |
| accelerate | Apache-2.0 | https://github.com/huggingface/accelerate | Model acceleration |
| pystray | LGPL-3.0 | https://github.com/moses-palmer/pystray | System tray icon |
| tqdm | MIT | https://github.com/tqdm/tqdm | Progress bars |
| requests | Apache-2.0 | https://github.com/psf/requests | HTTP downloads |
| PyInstaller | GPL with runtime exception | https://github.com/pyinstaller/pyinstaller | Optional packaging (build-time only) |

## Downloaded model weights (not bundled)

| Model | License | Notes |
|---|---|---|
| TripoSR checkpoint | MIT (model card) | Downloaded to `app/models/` on first run |
| DreamShaper 8 (Lykon) | CreativeML OpenRAIL-M | Commercial use permitted; applies to generated images |
| Stable Diffusion 1.5 | CreativeML OpenRAIL-M | Commercial use permitted with OpenRAIL terms |
| SD-Turbo / SDXL-Turbo | Stability AI Community License | Check terms before commercial use of generated images |
| u2net (rembg) | Apache-2.0 | Background removal model |

## Trademarks

Blender, Unity, Unreal, Claude, Cursor and other product names are trademarks of
their respective owners. MeshForge 3D is not affiliated with or endorsed by them.