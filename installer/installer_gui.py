"""
MeshForge 3D — Official Windows GUI Installer
=============================================
Automated 1-click installer:
- Selects installation directory
- Extracts and deploys MeshForge 3D studio
- Generates desktop and start menu shortcuts with brand icon
- Auto-launches the application upon completion
"""

import os
import sys
import shutil
import zipfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Determine resource path (works for dev and PyInstaller onefile)
def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "MeshForge3D")

def find_system_python():
    """Locates the true system pythonw.exe or python.exe (never the installer exe itself)."""
    for name in ["pythonw.exe", "python.exe", "py.exe"]:
        p = shutil.which(name)
        if p and "meshforge3d_setup" not in p.lower():
            dir_name = os.path.dirname(p)
            pw = os.path.join(dir_name, "pythonw.exe")
            if os.path.exists(pw):
                return pw
            return p

    local_app = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    candidates = [
        os.path.join(local_app, "Programs", "Python", "Python311", "pythonw.exe"),
        os.path.join(local_app, "Programs", "Python", "Python311", "python.exe"),
        os.path.join(local_app, "Programs", "Python", "Python310", "pythonw.exe"),
        os.path.join(local_app, "Programs", "Python", "Python310", "python.exe"),
        os.path.join(local_app, "Programs", "Python", "Python312", "pythonw.exe"),
        os.path.join(local_app, "Programs", "Python", "Python312", "python.exe"),
        r"C:\Python311\pythonw.exe",
        r"C:\Python311\python.exe",
        os.path.join(program_files, "Python311", "pythonw.exe"),
        os.path.join(program_files, "Python311", "python.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    return "pythonw.exe"


class MeshForgeInstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MeshForge 3D — Setup Wizard")
        self.root.geometry("580x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#0a0d14")

        # Set window icon if available
        icon_path = get_resource_path("MeshForge3D.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.install_dir = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.create_desktop_icon = tk.BooleanVar(value=True)
        self.launch_after_install = tk.BooleanVar(value=True)

        self._init_ui()

    def _init_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg="#111827", height=80)
        header.pack(fill="x", side="top")

        title_lbl = tk.Label(
            header,
            text="MeshForge 3D Studio Setup",
            font=("Segoe UI", 16, "bold"),
            fg="#00f0ff",
            bg="#111827",
        )
        title_lbl.pack(anchor="w", padx=20, pady=(15, 2))

        subtitle_lbl = tk.Label(
            header,
            text="Universal Image to 3D AI Reconstruction Studio v2.0",
            font=("Segoe UI", 9),
            fg="#9ca3af",
            bg="#111827",
        )
        subtitle_lbl.pack(anchor="w", padx=20, pady=(0, 10))

        # Main content area
        self.content = tk.Frame(self.root, bg="#0a0d14")
        self.content.pack(fill="both", expand=True, padx=25, pady=20)

        # Directory selection label
        dir_lbl = tk.Label(
            self.content,
            text="Select Destination Folder:",
            font=("Segoe UI", 10, "bold"),
            fg="#f3f4f6",
            bg="#0a0d14",
        )
        dir_lbl.pack(anchor="w", pady=(5, 5))

        dir_frame = tk.Frame(self.content, bg="#0a0d14")
        dir_frame.pack(fill="x", pady=(0, 15))

        self.dir_entry = tk.Entry(
            dir_frame,
            textvariable=self.install_dir,
            font=("Segoe UI", 10),
            bg="#1f2937",
            fg="#ffffff",
            insertbackground="#00f0ff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#374151",
            highlightcolor="#00f0ff",
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        browse_btn = tk.Button(
            dir_frame,
            text="Browse...",
            font=("Segoe UI", 9),
            bg="#374151",
            fg="#ffffff",
            activebackground="#4b5563",
            activeforeground="#ffffff",
            relief="flat",
            command=self._browse_dir,
            padx=12,
        )
        browse_btn.pack(side="right")

        # Options checkbuttons
        chk_desktop = tk.Checkbutton(
            self.content,
            text="Create Desktop Shortcut",
            variable=self.create_desktop_icon,
            font=("Segoe UI", 9),
            fg="#e5e7eb",
            bg="#0a0d14",
            activebackground="#0a0d14",
            activeforeground="#00f0ff",
            selectcolor="#1f2937",
        )
        chk_desktop.pack(anchor="w", pady=2)

        chk_launch = tk.Checkbutton(
            self.content,
            text="Launch MeshForge 3D immediately after installation",
            variable=self.launch_after_install,
            font=("Segoe UI", 9),
            fg="#e5e7eb",
            bg="#0a0d14",
            activebackground="#0a0d14",
            activeforeground="#00f0ff",
            selectcolor="#1f2937",
        )
        chk_launch.pack(anchor="w", pady=2)

        # Progress bar
        self.progress_lbl = tk.Label(
            self.content,
            text="Ready to install.",
            font=("Segoe UI", 9),
            fg="#9ca3af",
            bg="#0a0d14",
        )
        self.progress_lbl.pack(anchor="w", pady=(18, 4))

        self.progress_bar = ttk.Progressbar(
            self.content,
            orient="horizontal",
            mode="determinate",
            length=530,
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))

        # Bottom action bar
        self.bottom_bar = tk.Frame(self.root, bg="#111827", height=55)
        self.bottom_bar.pack(fill="x", side="bottom")

        self.install_btn = tk.Button(
            self.bottom_bar,
            text="Install MeshForge 3D",
            font=("Segoe UI", 10, "bold"),
            bg="#00f0ff",
            fg="#000000",
            activebackground="#38bdf8",
            activeforeground="#000000",
            relief="flat",
            padx=20,
            pady=6,
            command=self._start_installation,
        )
        self.install_btn.pack(side="right", padx=20, pady=10)

        self.cancel_btn = tk.Button(
            self.bottom_bar,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#374151",
            fg="#ffffff",
            activebackground="#4b5563",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=6,
            command=self.root.destroy,
        )
        self.cancel_btn.pack(side="right", padx=(0, 10), pady=10)

    def _browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.install_dir.get())
        if chosen:
            self.install_dir.set(chosen)

    def _start_installation(self):
        target_dir = self.install_dir.get().strip()
        if not target_dir:
            messagebox.showerror("Error", "Please specify a valid installation directory.")
            return

        self.install_btn.config(state="disabled", text="Installing...")
        self.cancel_btn.config(state="disabled")
        self.dir_entry.config(state="disabled")

        threading.Thread(target=self._perform_install, daemon=True).start()

    def _update_status(self, text, percent):
        self.progress_lbl.config(text=text)
        self.progress_bar["value"] = percent
        self.root.update_idletasks()

    def _perform_install(self):
        target_dir = self.install_dir.get().strip()
        try:
            self._update_status("Preparing directory...", 5)
            os.makedirs(target_dir, exist_ok=True)

            # Look for bundled package zip
            zip_path = get_resource_path("package.zip")
            if not os.path.exists(zip_path):
                # Fallback to local package in repo during development
                zip_path = os.path.join(os.path.abspath("."), "MeshForge3D_v2.0_Studio_Package.zip")

            if not os.path.exists(zip_path):
                raise FileNotFoundError(f"Installation payload not found: {zip_path}")

            self._update_status("Extracting MeshForge 3D files...", 15)
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.infolist()
                total = len(members)
                for idx, member in enumerate(members):
                    orig_filename = member.filename
                    if orig_filename.startswith("MeshForge3D/") or orig_filename.startswith("MeshForge3D\\"):
                        rel_name = orig_filename.split("/", 1)[-1].split("\\", 1)[-1]
                    else:
                        rel_name = orig_filename

                    if not rel_name:
                        continue

                    dest_path = os.path.normpath(os.path.join(target_dir, rel_name))
                    if member.is_dir() or orig_filename.endswith("/") or orig_filename.endswith("\\"):
                        os.makedirs(dest_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        with zf.open(member) as src_file, open(dest_path, "wb") as dst_file:
                            shutil.copyfileobj(src_file, dst_file)

                    percent = 15 + int((idx / max(1, total)) * 65)
                    if idx % 10 == 0:
                        self._update_status(f"Extracting: {os.path.basename(rel_name)}", percent)

            root_app_dir = os.path.normpath(target_dir)

            # Generate tailored MeshForge3D.vbs with detected Python interpreter
            runner_exe = find_system_python()
            main_py_path = os.path.normpath(os.path.join(root_app_dir, "app", "main.py"))
            vbs_file_path = os.path.normpath(os.path.join(root_app_dir, "MeshForge3D.vbs"))
            ico_file_path = os.path.normpath(os.path.join(root_app_dir, "MeshForge3D.ico"))
            print(f"[Installer] Target root: {root_app_dir}")
            print(f"[Installer] Selected Python runner: {runner_exe}")

            custom_vbs = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{root_app_dir}"
On Error Resume Next
WshShell.Run """{runner_exe}"" ""{main_py_path}"" --window", 0, False
If Err.Number <> 0 Then
    Err.Clear
    WshShell.Run "python app/main.py --window", 0, False
End If
'''
            try:
                with open(os.path.join(root_app_dir, "MeshForge3D.vbs"), "w", encoding="utf-8") as f:
                    f.write(custom_vbs)
            except Exception as e:
                print(f"VBS customizer notice: {e}")

            self._update_status("Configuring shortcuts & Windows environment...", 85)

            # Create Desktop Shortcut
            if self.create_desktop_icon.get():
                try:
                    self._create_shortcut(
                        target_path=os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "wscript.exe"),
                        arguments=f'"{vbs_file_path}"',
                        working_dir=root_app_dir,
                        icon_path=ico_file_path,
                        shortcut_name="MeshForge 3D Studio.lnk",
                        location="desktop"
                    )
                except Exception as exc:
                    print(f"Shortcut creation notice: {exc}")

            # Create Start Menu Shortcut
            try:
                self._create_shortcut(
                    target_path=os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "wscript.exe"),
                    arguments=f'"{vbs_file_path}"',
                    working_dir=root_app_dir,
                    icon_path=ico_file_path,
                    shortcut_name="MeshForge 3D.lnk",
                    location="start_menu"
                )
            except Exception as exc:
                print(f"Start menu creation notice: {exc}")

            self._update_status("Installation completed successfully!", 100)

            # Launch immediately if requested
            if self.launch_after_install.get():
                try:
                    if os.path.isabs(runner_exe) and os.path.exists(runner_exe):
                        subprocess.Popen(
                            [runner_exe, os.path.join(root_app_dir, "app", "main.py"), "--window"],
                            cwd=root_app_dir,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        )
                    else:
                        vbs_path = os.path.join(root_app_dir, "MeshForge3D.vbs")
                        if os.path.exists(vbs_path):
                            subprocess.Popen(["wscript.exe", vbs_path], cwd=root_app_dir)
                except Exception as exc:
                    print(f"Auto-launch notice: {exc}")

            self.install_btn.config(text="Finish", state="normal", command=self.root.destroy)

        except Exception as e:
            self._update_status(f"Error: {e}", 0)
            messagebox.showerror("Installation Error", f"Failed to install MeshForge 3D:\n{e}")
            self.install_btn.config(text="Retry", state="normal", command=self._start_installation)
            self.cancel_btn.config(state="normal")

    def _create_shortcut(self, target_path, arguments, working_dir, icon_path, shortcut_name, location="desktop"):
        # 1. Try native win32com COM interface with SpecialFolders (handles OneDrive and localized Desktop)
        try:
            from win32com.client import Dispatch
            ws = Dispatch("WScript.Shell")
            if location == "desktop":
                dest_dir = str(ws.SpecialFolders("Desktop"))
            else:
                dest_dir = str(ws.SpecialFolders("Programs"))
            
            os.makedirs(dest_dir, exist_ok=True)
            lnk_path = os.path.join(dest_dir, shortcut_name)
            
            s = ws.CreateShortcut(lnk_path)
            s.TargetPath = target_path
            s.Arguments = arguments
            s.WorkingDirectory = working_dir
            if icon_path and os.path.exists(icon_path):
                s.IconLocation = f"{icon_path},0"
            s.Description = "MeshForge 3D — Universal Image to 3D AI Studio"
            s.Save()
            if os.path.exists(lnk_path):
                print(f"[OK] Shortcut created via win32com at: {lnk_path}")
                return
        except Exception as exc:
            print(f"win32com shortcut notice: {exc}")

        # 2. Try PowerShell fallback
        try:
            if location == "desktop":
                dest_folder = "[Environment]::GetFolderPath('Desktop')"
            else:
                dest_folder = "[Environment]::GetFolderPath('Programs')"
            
            clean_args = arguments.replace('"', '`"')
            ps_script = f"""
            $ws = New-Object -ComObject WScript.Shell
            $folder = {dest_folder}
            $lnk = Join-Path $folder '{shortcut_name}'
            $s = $ws.CreateShortcut($lnk)
            $s.TargetPath = '{target_path}'
            $s.Arguments = '{clean_args}'
            $s.WorkingDirectory = '{working_dir}'
            $s.IconLocation = '{icon_path},0'
            $s.Description = 'MeshForge 3D — Universal Image to 3D AI Studio'
            $s.Save()
            """
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], check=True)
            return
        except Exception as exc:
            print(f"PowerShell shortcut notice: {exc}")

if __name__ == "__main__":
    app_root = tk.Tk()
    app = MeshForgeInstallerApp(app_root)
    app_root.mainloop()
