"""
MeshForge 3D — System Tray integration
=======================================
Runs in a background thread. When the user closes the browser window,
the app keeps working in the tray; "Open" re-opens the UI, "Quit"
fully shuts down the server.

Requires: pystray (in requirements.txt), Pillow.
"""

import threading
import webbrowser


class TrayIcon:
    def __init__(self, url: str, on_quit=None):
        self.url = url
        self.on_quit = on_quit or (lambda: None)
        self._icon = None
        self._thread = None

    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Start the tray icon thread. Returns False if pystray unavailable."""
        try:
            import pystray
            from PIL import Image, ImageDraw
            import os
        except ImportError:
            print("[Tray] pystray not installed - tray disabled.")
            return False

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "icon.ico")
        try:
            image = Image.open(icon_path)
        except Exception:
            # Fallback: simple cyan cube glyph
            image = Image.new("RGB", (64, 64), (10, 13, 20))
            d = ImageDraw.Draw(image)
            d.rectangle([2, 2, 61, 61], outline=(0, 240, 255), width=3)
            d.polygon([(32, 14), (48, 24), (32, 34), (16, 24)], outline=(0, 240, 255))
            d.polygon([(16, 24), (32, 34), (32, 52), (16, 42)], outline=(0, 240, 255))
            d.polygon([(48, 24), (32, 34), (32, 52), (48, 42)], outline=(0, 240, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Open MeshForge 3D", self._open, default=True),
            pystray.MenuItem("Quit", self._quit),
        )
        self._icon = pystray.Icon("MeshForge3D", image, "MeshForge 3D", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        print("[Tray] Tray icon active. Closing the window keeps the app running.")
        return True

    # ------------------------------------------------------------------
    def _open(self, icon=None, item=None):
        webbrowser.open(self.url)

    def _quit(self, icon=None, item=None):
        try:
            self._icon.stop()
        except Exception:
            pass
        self.on_quit()

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass