"""
MeshForge 3D — Mesh Processor
===============================
Handles post-processing, validation, statistics calculation,
and multi-format export (.glb, .obj, .stl, .ply) using trimesh and xatlas.
"""

import os
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

try:
    import trimesh
    _HAS_TRIMESH = True
except ImportError:
    _HAS_TRIMESH = False

try:
    import xatlas
    _HAS_XATLAS = True
except ImportError:
    _HAS_XATLAS = False


class MeshProcessor:
    """Post-processes 3D meshes and exports to various 3D file formats."""

    def __init__(self) -> None:
        if not _HAS_TRIMESH:
            raise ImportError(
                "trimesh is required for MeshProcessor. "
                "Install with: pip install trimesh"
            )

    def clean_mesh(self, mesh: "trimesh.Trimesh", smooth: bool = True) -> "trimesh.Trimesh":
        """Clean, filter floating debris, and apply Taubin surface smoothing to eliminate voxel artifacts."""
        try:
            if hasattr(mesh, "remove_unreferenced_vertices"):
                mesh.remove_unreferenced_vertices()
        except Exception:
            pass

        try:
            if hasattr(mesh, "remove_infinite_values"):
                mesh.remove_infinite_values()
        except Exception:
            pass

        # Step 1: Remove small disconnected floating debris blobs
        try:
            components = mesh.split(only_watertight=False)
            if len(components) > 1:
                max_faces = max(len(c.faces) for c in components)
                # Keep significant bodies (>= 2% of the main mesh)
                valid = [c for c in components if len(c.faces) >= max(30, int(max_faces * 0.02))]
                if valid:
                    mesh = trimesh.util.concatenate(valid)
        except Exception:
            pass

        # Step 2: Taubin volume-preserving surface smoothing
        if smooth:
            try:
                import trimesh.smoothing
                mesh = trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=-0.52, iterations=6)
            except Exception:
                pass

        # Step 3: Recalculate smooth normals
        try:
            if hasattr(mesh, "fix_normals"):
                mesh.fix_normals(multibody=True)
        except Exception:
            pass

        return mesh

    def get_mesh_stats(self, mesh: "trimesh.Trimesh") -> Dict[str, Any]:
        """Compute geometry statistics for the UI inspector."""
        bounds = mesh.bounds if hasattr(mesh, "bounds") and mesh.bounds is not None else np.zeros((2, 3))
        dimensions = bounds[1] - bounds[0] if len(bounds) == 2 else np.zeros(3)

        return {
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
            "is_watertight": bool(mesh.is_watertight) if hasattr(mesh, "is_watertight") else False,
            "dimensions": [round(float(d), 3) for d in dimensions],
        }

    def export_glb(
        self,
        mesh: "trimesh.Trimesh",
        output_path: str,
        bake_output: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Export mesh as binary glTF (.glb) with embedded UV texture or vertex colors."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if bake_output is not None:
            vmapping = bake_output["vmapping"]
            indices = bake_output["indices"]
            uvs = bake_output["uvs"]
            colors = bake_output["colors"]

            tex_img = Image.fromarray((colors * 255.0).astype(np.uint8)).transpose(
                Image.FLIP_TOP_BOTTOM
            )
            material = trimesh.visual.material.PBRMaterial(
                baseColorTexture=tex_img,
                metallicFactor=0.0,
                roughnessFactor=0.7,
                doubleSided=True,
            )
            visuals = trimesh.visual.TextureVisuals(
                uv=uvs,
                material=material,
            )
            textured_mesh = trimesh.Trimesh(
                vertices=mesh.vertices[vmapping],
                faces=indices,
                visual=visuals,
                process=False,
            )
            textured_mesh.export(output_path, file_type="glb")
        else:
            mesh = self.clean_mesh(mesh)
            mesh.export(output_path, file_type="glb")
        return output_path

    def export_obj(
        self,
        mesh: "trimesh.Trimesh",
        output_path: str,
        bake_output: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Export mesh as Wavefront .obj (with baked texture if provided)."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if bake_output is not None and _HAS_XATLAS:
            # Export with UV map and texture atlas
            vmapping = bake_output["vmapping"]
            indices = bake_output["indices"]
            uvs = bake_output["uvs"]
            colors = bake_output["colors"]

            tex_path = os.path.splitext(output_path)[0] + ".png"
            tex_img = Image.fromarray((colors * 255.0).astype(np.uint8)).transpose(
                Image.FLIP_TOP_BOTTOM
            )
            tex_img.save(tex_path)

            xatlas.export(
                output_path,
                mesh.vertices[vmapping],
                indices,
                uvs,
                mesh.vertex_normals[vmapping],
            )
        else:
            mesh = self.clean_mesh(mesh)
            mesh.export(output_path, file_type="obj")

        return output_path

    def export_stl(self, mesh: "trimesh.Trimesh", output_path: str) -> str:
        """Export mesh as binary STL for 3D printing."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mesh = self.clean_mesh(mesh)
        mesh.export(output_path, file_type="stl")
        return output_path

    def export_ply(self, mesh: "trimesh.Trimesh", output_path: str) -> str:
        """Export mesh as binary PLY."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        mesh = self.clean_mesh(mesh)
        mesh.export(output_path, file_type="ply")
        return output_path