"""
MeshForge 3D — Image Preprocessor
===================================
Uses official TripoSR foreground cropping, square padding, and alpha-blending
over neutral gray (0.5 = RGB 128, 128, 128) conditioning canvas.
"""

import traceback
from typing import Optional, Tuple

import numpy as np
import PIL.Image
from PIL import Image

try:
    import rembg
    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False


class ImagePreprocessor:
    """Preprocesses input images with precise TripoSR foreground ratio & background handling."""

    DEFAULT_FOREGROUND_RATIO: float = 0.85

    def __init__(self) -> None:
        self._session: Optional[object] = None

    def _ensure_session(self) -> None:
        """Lazily initialise the rembg session on CPU."""
        if self._session is not None:
            return
        if not _REMBG_AVAILABLE:
            raise RuntimeError("rembg is not installed. Run: pip install rembg")
        try:
            self._session = rembg.new_session(
                "u2net", providers=["CPUExecutionProvider"]
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialise rembg session: {exc}"
            ) from exc

    def remove_background(self, image: Image.Image) -> Image.Image:
        """Remove background using rembg if image is not already transparent."""
        self._ensure_session()
        # Check if already transparent
        if image.mode == "RGBA":
            extrema = image.getextrema()
            if len(extrema) == 4 and extrema[3][0] < 240:
                # Image already has real transparency
                return image

        if image.mode != "RGB":
            image = image.convert("RGB")

        try:
            rgba = rembg.remove(image, session=self._session)
            if rgba.mode != "RGBA":
                rgba = rgba.convert("RGBA")
            return rgba
        except Exception as exc:
            print(f"[Preprocessor] rembg warning: {exc}, fallback to RGBA")
            return image.convert("RGBA")

    @staticmethod
    def resize_and_pad_foreground(image: Image.Image, ratio: float = 0.85) -> Image.Image:
        """Crop non-zero alpha region, pad to square, and scale according to ratio."""
        arr = np.array(image)
        if arr.ndim != 3 or arr.shape[-1] != 4:
            return image.convert("RGBA").resize((512, 512), Image.LANCZOS)

        alpha = np.where(arr[..., 3] > 0)
        if len(alpha[0]) == 0 or len(alpha[1]) == 0:
            return image.resize((512, 512), Image.LANCZOS)

        y1, y2 = int(alpha[0].min()), int(alpha[0].max()) + 1
        x1, x2 = int(alpha[1].min()), int(alpha[1].max()) + 1

        # Crop foreground
        fg = arr[y1:y2, x1:x2]
        size = max(fg.shape[0], fg.shape[1])

        ph0, pw0 = (size - fg.shape[0]) // 2, (size - fg.shape[1]) // 2
        ph1, pw1 = size - fg.shape[0] - ph0, size - fg.shape[1] - pw0

        new_image = np.pad(
            fg,
            ((ph0, ph1), (pw0, pw1), (0, 0)),
            mode="constant",
            constant_values=((0, 0), (0, 0), (0, 0)),
        )

        # Compute padding according to foreground ratio
        new_size = max(size, int(new_image.shape[0] / max(ratio, 0.1)))
        ph0, pw0 = (new_size - size) // 2, (new_size - size) // 2
        ph1, pw1 = new_size - size - ph0, new_size - size - pw0

        new_image = np.pad(
            new_image,
            ((ph0, ph1), (pw0, pw1), (0, 0)),
            mode="constant",
            constant_values=((0, 0), (0, 0), (0, 0)),
        )

        pil_img = Image.fromarray(new_image)
        return pil_img.resize((512, 512), Image.LANCZOS)

    def process_for_model(
        self,
        image: Image.Image,
        foreground_ratio: float = DEFAULT_FOREGROUND_RATIO,
        remove_bg: bool = True,
    ) -> Tuple[Image.Image, Image.Image]:
        """Preprocess an input image into a 512x512 RGB model input with neutral gray background."""
        # Check if image already has transparent alpha
        has_alpha = False
        if image.mode == "RGBA":
            extrema = image.getextrema()
            if len(extrema) == 4 and extrema[3][0] < 240:
                has_alpha = True

        if remove_bg:
            rgba = self.remove_background(image)
        elif has_alpha:
            rgba = image.copy()
        else:
            # remove_bg is False, but image is completely opaque.
            # If corners are near-white/near-black/uniform, mask the background to prevent solid bounding cube.
            rgba = image.convert("RGBA")
            arr = np.array(rgba)
            h, w = arr.shape[:2]
            corner_size = max(8, min(h, w) // 16)
            corners = np.concatenate([
                arr[:corner_size, :corner_size],
                arr[:corner_size, -corner_size:],
                arr[-corner_size:, :corner_size],
                arr[-corner_size:, -corner_size:]
            ])
            corner_mean = corners[:, :, :3].mean(axis=(0, 1))
            corner_std = corners[:, :, :3].std(axis=(0, 1)).mean()

            if corner_std < 30:  # Uniform corner background (e.g. white, light gray, black)
                diff = np.abs(arr[:, :, :3].astype(np.float32) - corner_mean).max(axis=-1)
                alpha_mask = np.clip((diff - 15) / 25.0 * 255.0, 0, 255).astype(np.uint8)
                arr[:, :, 3] = np.minimum(arr[:, :, 3], alpha_mask)
                rgba = Image.fromarray(arr)
            else:
                # Busy background: isolate with rembg to prevent cube explosion
                try:
                    rgba = self.remove_background(image)
                except Exception:
                    rgba = image.convert("RGBA")

        # Resize and center foreground with padding
        padded_rgba = self.resize_and_pad_foreground(rgba, foreground_ratio)

        # Smart detail & edge sharpening to enhance neural triplane attention
        try:
            from PIL import ImageFilter, ImageEnhance
            # Sharpen RGB while preserving alpha
            r, g, b, a = padded_rgba.split()
            rgb_img = Image.merge("RGB", (r, g, b))
            rgb_sharp = rgb_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=3))
            # Boost subtle contrast
            rgb_enhanced = ImageEnhance.Contrast(rgb_sharp).enhance(1.05)
            r_s, g_s, b_s = rgb_enhanced.split()
            padded_rgba = Image.merge("RGBA", (r_s, g_s, b_s, a))
        except Exception:
            pass

        # Alpha-blend onto neutral gray (0.5 = 128)
        img_np = np.array(padded_rgba).astype(np.float32) / 255.0
        rgb = img_np[:, :, :3] * img_np[:, :, 3:4] + (1.0 - img_np[:, :, 3:4]) * 0.5
        model_input = Image.fromarray(np.clip(rgb * 255.0, 0, 255).astype(np.uint8))

        return model_input, padded_rgba