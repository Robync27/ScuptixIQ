# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:/3dmodel_app/MeshForge3D/app/ui', 'ui'), ('C:/3dmodel_app/MeshForge3D/tsr_sdk', 'tsr_sdk'), ('C:/3dmodel_app/MeshForge3D/installer/LICENSE.txt', 'licenses/LICENSE.txt'), ('C:/3dmodel_app/MeshForge3D/app/models', 'models')]
binaries = []
hiddenimports = ['eel', 'eel.browsers', 'safetensors', 'huggingface_hub', 'rembg', 'trimesh', 'mcubes', 'xatlas', 'moderngl', 'scipy', 'skimage', 'PIL', 'numpy', 'cv2']
tmp_ret = collect_all('rembg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('trimesh')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('eel')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:/3dmodel_app/MeshForge3D/app/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'transformers', 'diffusers', 'accelerate', 'tkinter', 'matplotlib', 'IPython', 'jupyter', 'notebook', 'pytest', 'PyQt5', 'PySide2', 'PySide6', 'pandas', 'sympy', 'pydoc_data'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MeshForge3D',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:/3dmodel_app/MeshForge3D/version_info.txt',
    icon=['C:/3dmodel_app/MeshForge3D/MeshForge3D.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MeshForge3D',
)
