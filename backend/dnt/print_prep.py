"""
Print preparation for D&T Sketch-to-3D.

Takes the mesh the AI engine produced and makes it ready for a small classroom
3D print:

1. turn it so it stands upright (Z up)
2. remove tiny loose fragments (AI noise) but keep and report real parts
3. scale it uniformly to fit the maximum print box (default 40 x 40 x 60 mm)
4. optionally give it a flat base (flatten the bottom, or add a plinth)
5. run printability checks and return a report the student and teacher can read

Only CPU libraries are used (trimesh, numpy, scipy, manifold3d), so this whole
module runs and is tested without a GPU.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np
import trimesh

from .config import DntSettings, get_settings

logger = logging.getLogger("pixform.dnt")

BASE_MODES = ("none", "flatten", "plinth")
STATUS_ORDER = {"pass": 0, "info": 0, "skipped": 1, "warn": 2, "fail": 3}


# ---------------------------------------------------------------------------
# Geometry steps
# ---------------------------------------------------------------------------

def orient_up(mesh: trimesh.Trimesh, up_axis: str = "z") -> trimesh.Trimesh:
    """Rotate the mesh so the given axis points up (+Z). Accepts x, y, z, -x, -y, -z."""
    axis = (up_axis or "z").strip().lower()
    vectors = {
        "x": [1, 0, 0], "-x": [-1, 0, 0],
        "y": [0, 1, 0], "-y": [0, -1, 0],
        "z": [0, 0, 1], "-z": [0, 0, -1],
    }
    if axis not in vectors or axis == "z":
        return mesh
    rot = trimesh.geometry.align_vectors(vectors[axis], [0, 0, 1])
    mesh = mesh.copy()
    mesh.apply_transform(rot)
    return mesh


def rotate_mesh(mesh: trimesh.Trimesh, rotate_deg=(0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    """Rotate about X, then Y, then Z (degrees), around the mesh centre."""
    rx, ry, rz = (float(a or 0.0) for a in rotate_deg)
    if not (rx or ry or rz):
        return mesh
    mesh = mesh.copy()
    centre = mesh.bounding_box.centroid
    rot = trimesh.transformations.euler_matrix(np.radians(rx), np.radians(ry), np.radians(rz), axes="sxyz")
    mesh.apply_translation(-centre)
    mesh.apply_transform(rot)
    mesh.apply_translation(centre)
    return mesh


def remove_debris(mesh: trimesh.Trimesh, fraction: float) -> Tuple[trimesh.Trimesh, int, int]:
    """Drop loose fragments smaller than `fraction` of the largest part (by surface area).

    Returns (mesh, removed_count, kept_parts). Real parts such as a detached arm are
    kept so the checks can tell the student about them, instead of silently deleting them.
    """
    try:
        parts = mesh.split(only_watertight=False)
    except Exception as e:  # pragma: no cover - split needs scipy or networkx
        logger.warning("Could not split mesh into parts: %s", e)
        return mesh, 0, 1
    if len(parts) <= 1:
        return mesh, 0, 1
    areas = np.array([p.area for p in parts])
    keep = areas >= areas.max() * fraction
    kept = [p for p, k in zip(parts, keep) if k]
    removed = int((~keep).sum())
    merged = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]
    return merged, removed, len(kept)


def fit_to_box(mesh: trimesh.Trimesh, box: Tuple[float, float, float], reserve_z: float = 0.0) -> Tuple[trimesh.Trimesh, float]:
    """Scale uniformly so the mesh fits inside `box` (mm), centre it on X/Y and stand it on Z=0.

    `reserve_z` keeps that many millimetres of height free (for a plinth added later).
    Returns (mesh, scale_factor).
    """
    mesh = mesh.copy()
    ext = np.asarray(mesh.extents, dtype=float)
    if np.any(ext <= 0) or not np.all(np.isfinite(ext)):
        raise ValueError("Mesh has no size; cannot scale it")
    limits = np.array([box[0], box[1], max(box[2] - reserve_z, 1e-3)], dtype=float)
    scale = float(np.min(limits / ext))
    lo = mesh.bounds[0]
    hi = mesh.bounds[1]
    centre = np.array([(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2]])
    mesh.apply_translation(-centre)
    mesh.apply_scale(scale)
    return mesh, scale


def _stand_on_floor(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2.0, -(lo[1] + hi[1]) / 2.0, -lo[2]])
    return mesh


def _boolean(op: str, meshes):
    if op == "union":
        return trimesh.boolean.union(meshes, engine="manifold")
    return trimesh.boolean.intersection(meshes, engine="manifold")


def flatten_bottom(mesh: trimesh.Trimesh, depth_mm: float) -> trimesh.Trimesh:
    """Slice a thin layer off the bottom so the model sits on a flat face."""
    lo, hi = mesh.bounds
    pad = 5.0
    size = (hi - lo) + 2 * pad
    keeper = trimesh.creation.box(extents=[size[0], size[1], (hi[2] - lo[2]) - depth_mm + pad])
    keeper.apply_translation([
        (lo[0] + hi[0]) / 2.0,
        (lo[1] + hi[1]) / 2.0,
        lo[2] + depth_mm + keeper.extents[2] / 2.0,
    ])
    cut = _boolean("intersection", [mesh, keeper])
    if cut.is_empty or len(cut.faces) == 0:
        raise ValueError("Flattening removed the whole model")
    return _stand_on_floor(cut)


def add_plinth(mesh: trimesh.Trimesh, height_mm: float, margin_mm: float,
               max_radius_mm: float) -> trimesh.Trimesh:
    """Add a round plinth under the model. The model must already stand on Z=0."""
    lo = mesh.bounds[0]
    v = mesh.vertices
    footprint = v[v[:, 2] <= lo[2] + max(1.0, height_mm)]
    if len(footprint) == 0:
        footprint = v
    centre_xy = (footprint[:, :2].max(axis=0) + footprint[:, :2].min(axis=0)) / 2.0
    radius = float(np.linalg.norm(footprint[:, :2] - centre_xy, axis=1).max()) + margin_mm
    # A plinth only as wide as the contact patch does little for stability, so make it
    # at least ~90% of the model's widest side, but never wider than the print box.
    widest = float(max(mesh.extents[0], mesh.extents[1]))
    radius = min(max(radius, 0.45 * widest, 3.0), max_radius_mm)
    overlap = min(0.5, height_mm / 2.0)
    disc = trimesh.creation.cylinder(radius=radius, height=height_mm + overlap, sections=96)
    disc.apply_translation([centre_xy[0], centre_xy[1], lo[2] - height_mm + (height_mm + overlap) / 2.0])
    joined = _boolean("union", [mesh, disc])
    return _stand_on_floor(joined)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check(name: str, label: str, status: str, message: str, **values) -> dict:
    return {"id": name, "label": label, "status": status, "message": message, **values}


def check_dimensions(mesh: trimesh.Trimesh, box) -> dict:
    ext = [round(float(e), 2) for e in mesh.extents]
    ok = all(e <= b + 0.01 for e, b in zip(ext, box))
    msg = (f"{ext[0]} x {ext[1]} x {ext[2]} mm fits inside {box[0]:g} x {box[1]:g} x {box[2]:g} mm."
           if ok else
           f"{ext[0]} x {ext[1]} x {ext[2]} mm is bigger than the {box[0]:g} x {box[1]:g} x {box[2]:g} mm limit.")
    return _check("size", "Size", "pass" if ok else "fail", msg, size_mm=ext, max_mm=list(box))


def _edge_face_counts(mesh: trimesh.Trimesh) -> np.ndarray:
    if len(mesh.faces) == 0:
        return np.zeros(0, dtype=int)
    _, counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
    return counts


def check_watertight(mesh: trimesh.Trimesh) -> dict:
    counts = _edge_face_counts(mesh)
    open_edges = int((counts == 1).sum())
    if mesh.is_watertight:
        return _check("watertight", "Closed surface (watertight)", "pass",
                      "The surface is fully closed, so the slicer can tell inside from outside.",
                      open_edges=0)
    return _check("watertight", "Closed surface (watertight)", "fail",
                  f"The surface has {open_edges} open edges (holes). The slicer may fill or skip parts.",
                  open_edges=open_edges)


def check_manifold(mesh: trimesh.Trimesh) -> dict:
    counts = _edge_face_counts(mesh)
    bad_edges = int((counts > 2).sum())
    winding_ok = bool(mesh.is_winding_consistent)
    if bad_edges == 0 and winding_ok:
        return _check("manifold", "Clean geometry (manifold)", "pass",
                      "Every edge joins exactly two faces and all faces point the same way.",
                      non_manifold_edges=0, winding_consistent=True)
    problems = []
    if bad_edges:
        problems.append(f"{bad_edges} edges are shared by more than two faces")
    if not winding_ok:
        problems.append("some faces point the wrong way")
    return _check("manifold", "Clean geometry (manifold)", "fail",
                  "Geometry problem: " + "; ".join(problems) + ".",
                  non_manifold_edges=bad_edges, winding_consistent=winding_ok)


def check_components(mesh: trimesh.Trimesh, removed_debris: int = 0) -> dict:
    try:
        n = len(mesh.split(only_watertight=False))
    except Exception:
        n = 1
    extra = f" ({removed_debris} tiny loose fragments were cleaned away.)" if removed_debris else ""
    if n <= 1:
        return _check("parts", "One connected piece", "pass",
                      "The model is one connected piece." + extra,
                      parts=n, debris_removed=removed_debris)
    return _check("parts", "One connected piece", "warn",
                  f"The model is in {n} separate pieces. Loose pieces will print separately or fall over. "
                  "Join them in your design, or check with your teacher." + extra,
                  parts=n, debris_removed=removed_debris)


def _fill_voxels(mesh: trimesh.Trimesh, pitch: float) -> Tuple[np.ndarray, np.ndarray]:
    """Solid voxel grid of the mesh. Returns (bool grid, origin of voxel [0,0,0] in mm)."""
    lo, hi = mesh.bounds
    pad = 2
    shape = np.ceil((hi - lo) / pitch).astype(int) + 1 + 2 * pad
    origin = lo - pad * pitch
    # Sample voxel centres column by column with ray casting along Z (parity rule).
    xs = origin[0] + (np.arange(shape[0]) + 0.5) * pitch
    ys = origin[1] + (np.arange(shape[1]) + 0.5) * pitch
    zs = origin[2] + (np.arange(shape[2]) + 0.5) * pitch
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    ray_origins = np.column_stack([gx.ravel(), gy.ravel(), np.full(gx.size, origin[2] - pitch)])
    ray_dirs = np.tile([0.0, 0.0, 1.0], (len(ray_origins), 1))
    locs, ray_idx, _ = mesh.ray.intersects_location(ray_origins, ray_dirs, multiple_hits=True)
    grid = np.zeros(shape, dtype=bool)
    if len(ray_idx) == 0:
        return grid, origin
    order = np.lexsort((locs[:, 2], ray_idx))
    ray_idx = ray_idx[order]
    hz = locs[order, 2]
    starts = np.flatnonzero(np.r_[True, ray_idx[1:] != ray_idx[:-1]])
    ends = np.r_[starts[1:], len(ray_idx)]
    for s, e in zip(starts, ends):
        hits = np.unique(np.round(hz[s:e], 6))
        if len(hits) < 2:
            continue
        r = ray_idx[s]
        ix, iy = divmod(int(r), shape[1])
        for a, b in zip(hits[0::2], hits[1::2]):
            k0 = int(np.ceil((a - origin[2]) / pitch - 0.5))
            k1 = int(np.floor((b - origin[2]) / pitch - 0.5))
            if k1 >= k0:
                grid[ix, iy, max(k0, 0):min(k1, shape[2] - 1) + 1] = True
    return grid, origin


def check_thickness(mesh: trimesh.Trimesh, settings: DntSettings) -> dict:
    """Estimate regions thinner than the minimum printable thickness.

    Method: fill the model with small cubes (voxels), then do a morphological
    "opening" with a ball whose diameter is the minimum thickness. Any material
    the ball cannot reach is thinner than the minimum. It is an estimate: results
    are accurate to about one voxel (default 0.2 mm).
    """
    t = settings.min_thickness_mm
    label = f"Thick enough to print (at least {t:g} mm)"
    if not mesh.is_watertight:
        return _check("thickness", label, "skipped",
                      "Skipped because the surface is not closed. Fix that first.",
                      min_thickness_mm=t)
    from scipy import ndimage

    pitch = settings.thickness_voxel_mm
    grid, origin = _fill_voxels(mesh, pitch)
    solid = int(grid.sum())
    if solid == 0:
        return _check("thickness", label, "skipped", "Could not measure the inside of the model.",
                      min_thickness_mm=t)
    r = t / 2.0
    inside_dist = ndimage.distance_transform_edt(grid) * pitch
    core = inside_dist > r
    reach = ndimage.distance_transform_edt(~core) * pitch <= r + 1e-9
    thin = grid & ~reach
    thin_fraction = float(thin.sum()) / solid

    labels, n = ndimage.label(thin)
    voxel_mm3 = pitch ** 3
    regions = []
    if n:
        sizes = ndimage.sum(thin, labels, index=np.arange(1, n + 1))
        min_region_mm3 = max(2.0, (t ** 3))
        for i in np.argsort(-sizes):
            vol = float(sizes[i]) * voxel_mm3
            if vol < min_region_mm3:
                break
            zz = np.nonzero(labels == i + 1)[2]
            z_lo = float(origin[2] + zz.min() * pitch)
            z_hi = float(origin[2] + (zz.max() + 1) * pitch)
            regions.append({"volume_mm3": round(vol, 1), "z_from_mm": round(max(z_lo, 0.0), 1),
                            "z_to_mm": round(z_hi, 1)})
            if len(regions) >= 5:
                break

    values = dict(min_thickness_mm=t, thin_fraction=round(thin_fraction, 4),
                  thin_regions=regions, voxel_mm=pitch)
    if not regions and thin_fraction <= settings.thin_volume_warn_fraction:
        return _check("thickness", label, "pass",
                      f"No parts thinner than about {t:g} mm were found.", **values)
    where = ", ".join(f"{r_['z_from_mm']}-{r_['z_to_mm']} mm up" for r_ in regions[:3]) or "small areas"
    return _check("thickness", label, "warn",
                  f"Some parts look thinner than {t:g} mm and may break or not print ({where}). "
                  "Make them thicker in your design.", **values)


def run_checks(mesh: trimesh.Trimesh, settings: Optional[DntSettings] = None,
               removed_debris: int = 0) -> dict:
    settings = settings or get_settings()
    checks = [
        check_dimensions(mesh, settings.max_box_mm),
        check_watertight(mesh),
        check_manifold(mesh),
        check_components(mesh, removed_debris),
    ]
    try:
        checks.append(check_thickness(mesh, settings))
    except Exception as e:  # never let an estimate block the result
        logger.warning("Thickness check failed: %s", e)
        checks.append(_check("thickness", "Thick enough to print", "skipped",
                             f"The thickness estimate could not run ({e}).",
                             min_thickness_mm=settings.min_thickness_mm))
    worst = max((STATUS_ORDER.get(c["status"], 0) for c in checks), default=0)
    overall = {0: "pass", 1: "pass", 2: "warn", 3: "fail"}[worst]
    volume = float(abs(mesh.volume)) / 1000.0 if mesh.is_watertight else None
    return {
        "overall": overall,
        "checks": checks,
        "size_mm": [round(float(e), 2) for e in mesh.extents],
        "volume_cm3": round(volume, 2) if volume is not None else None,
        "faces": int(len(mesh.faces)),
    }


# ---------------------------------------------------------------------------
# Whole pipeline
# ---------------------------------------------------------------------------

def prepare_for_print(mesh: trimesh.Trimesh, base_mode: str = "none", up_axis: str = "z",
                      settings: Optional[DntSettings] = None, rotate_deg=(0.0, 0.0, 0.0),
                      size_percent: float = 100.0) -> Tuple[trimesh.Trimesh, dict]:
    """Orient, clean, scale, add base, then check. Returns (print-ready mesh, report).

    rotate_deg: student rotation (X, Y, Z degrees) applied after the automatic up-axis turn.
    size_percent: 100 = largest size that fits the print box; 50 = half that size.
    """
    settings = settings or get_settings()
    base_mode = (base_mode or "none").strip().lower()
    if base_mode not in BASE_MODES:
        raise ValueError(f"base_mode must be one of {BASE_MODES}")
    size_percent = float(size_percent)
    if not (10.0 <= size_percent <= 100.0):
        raise ValueError("size_percent must be between 10 and 100")
    notes = []
    max_box = settings.max_box_mm
    box = tuple(b * size_percent / 100.0 for b in max_box)

    mesh = orient_up(mesh, up_axis)
    mesh = rotate_mesh(mesh, rotate_deg)
    mesh, removed, kept_parts = remove_debris(mesh, settings.debris_volume_fraction)
    if removed:
        notes.append(f"Removed {removed} tiny loose fragments.")

    reserve = settings.base_plinth_height_mm if base_mode == "plinth" else 0.0
    mesh, scale = fit_to_box(mesh, box, reserve_z=reserve)

    base_applied = "none"
    if base_mode in {"flatten", "plinth"}:
        try:
            depth = max(0.5, mesh.extents[2] * settings.base_flatten_depth_fraction)
            mesh = flatten_bottom(mesh, depth)
            base_applied = "flatten"
            if base_mode == "plinth":
                max_r = min(box[0], box[1]) / 2.0
                mesh = add_plinth(mesh, settings.base_plinth_height_mm,
                                  settings.base_plinth_margin_mm, max_r)
                base_applied = "plinth"
        except Exception as e:
            notes.append(f"The flat base could not be added ({e}). Usually this means the "
                         "surface is not closed yet.")
            logger.warning("Base step failed: %s", e)
        # Base work changes the size slightly. A flattened model is re-fitted so it uses the
        # full height again; a plinth model is only shrunk if it no longer fits.
        if base_applied == "flatten" or np.any(mesh.extents > np.array(box) + 1e-6):
            mesh, extra = fit_to_box(mesh, box)
            scale *= extra
        else:
            mesh = _stand_on_floor(mesh)

    report = run_checks(mesh, settings, removed_debris=removed)
    report.update({
        "rotate_deg": [float(a or 0.0) for a in rotate_deg],
        "size_percent": size_percent,
        "scale_factor": round(scale, 6),
        "base_requested": base_mode,
        "base_applied": base_applied,
        "up_axis": up_axis,
        "notes": notes,
    })
    return mesh, report
