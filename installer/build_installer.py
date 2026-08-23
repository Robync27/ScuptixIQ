import os
import shutil
import subprocess

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
installer_script = os.path.join(root_dir, "installer", "installer_gui.py")
package_zip = os.path.join(root_dir, "MeshForge3D_v2.0_Studio_Package.zip")
icon_file = os.path.join(root_dir, "MeshForge3D.ico")

# Ensure package zip exists
if not os.path.exists(package_zip):
    print("Building package zip first...")
    subprocess.run(["python", os.path.join(root_dir, "package_light.py")], check=True)

# Copy zip as package.zip for bundling
bundled_zip = os.path.join(root_dir, "installer", "package.zip")
shutil.copyfile(package_zip, bundled_zip)

print("Compiling MeshForge3D_Setup.exe via PyInstaller...")
cmd = [
    "pyinstaller",
    "--noconsole",
    "--onefile",
    f"--icon={icon_file}",
    f"--add-data={bundled_zip};.",
    f"--add-data={icon_file};.",
    "--hidden-import=win32com",
    "--hidden-import=win32com.client",
    "--name=MeshForge3D_Setup",
    f"--distpath={root_dir}",
    "--workpath=installer/build",
    "--specpath=installer",
    "-y",
    installer_script,
]

subprocess.run(cmd, check=True)

# Cleanup temp files
if os.path.exists(bundled_zip):
    os.remove(bundled_zip)

output_exe = os.path.join(root_dir, "MeshForge3D_Setup.exe")
if os.path.exists(output_exe):
    size_mb = os.path.getsize(output_exe) / (1024 * 1024)
    print(f"\n[SUCCESS] Standalone Installer compiled successfully!")
    print(f"File: {output_exe} ({size_mb:.2f} MB)")
else:
    print("[ERROR] Output executable not found.")
