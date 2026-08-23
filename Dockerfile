# MeshForge 3D — Docker Image
# =============================
# Multi-stage Linux container with ONNX Runtime CPU inference.
# Zero CUDA. Zero PyTorch. Pure ONNX + DirectML/CPU pipeline.
#
# Build:  docker build -t meshforge3d .
# Run:    docker run -it --rm -p 7860:7860 meshforge3d

FROM python:3.10-slim AS base

# System dependencies for OpenCV, rembg, and trimesh
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libxrender1 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# -------------------------------------------------------------------
# Install Python dependencies
# -------------------------------------------------------------------
# CRITICAL: Absolutely NO torch, torchvision, or CUDA packages.
# Inference runs exclusively via onnxruntime (CPU provider in Docker).
# -------------------------------------------------------------------
RUN pip install --no-cache-dir \
    onnxruntime \
    numpy>=1.24.0 \
    Pillow>=10.0.0 \
    opencv-python-headless>=4.8.0 \
    scikit-image>=0.21.0 \
    rembg>=2.0.50 \
    trimesh>=4.0.0 \
    PyMCubes>=0.1.4 \
    xatlas>=0.0.7 \
    eel>=0.16.0 \
    huggingface-hub>=0.20.0 \
    tqdm>=4.66.0 \
    requests>=2.31.0 \
    scipy>=1.10.0

# -------------------------------------------------------------------
# Copy application code
# -------------------------------------------------------------------
COPY app/ ./app/

# Create output directory
RUN mkdir -p /app/app/ui/outputs /app/app/models

# Expose the Eel web server port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

# Run the application
CMD ["python", "app/main.py"]