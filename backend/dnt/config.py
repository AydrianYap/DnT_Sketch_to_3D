"""
D&T Sketch-to-3D settings.

Every limit the classroom pipeline relies on lives here, so a teacher can see
and change them in one place. Each value can be overridden with an environment
variable (shown next to it) without editing code.
"""
import os
from dataclasses import dataclass, field
from typing import Tuple


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_list(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return tuple(p.strip() for p in raw.replace(";", ",").split(",") if p.strip())


@dataclass(frozen=True)
class DntSettings:
    # Maximum printed size in millimetres: width (X) x depth (Y) x height (Z).
    # The model is scaled uniformly (proportions kept) to fit inside this box.
    max_x_mm: float = field(default_factory=lambda: _env_float("DNT_MAX_X_MM", 40.0))
    max_y_mm: float = field(default_factory=lambda: _env_float("DNT_MAX_Y_MM", 40.0))
    max_z_mm: float = field(default_factory=lambda: _env_float("DNT_MAX_Z_MM", 60.0))

    # Thinnest wall or limb the printer can reliably make. 1.2 mm suits a
    # standard 0.4 mm FDM nozzle (three perimeter lines). The check is an estimate.
    min_thickness_mm: float = field(default_factory=lambda: _env_float("DNT_MIN_THICKNESS_MM", 1.2))
    # Voxel size used by the thickness estimate. Smaller = more accurate, slower.
    thickness_voxel_mm: float = field(default_factory=lambda: _env_float("DNT_THICKNESS_VOXEL_MM", 0.2))
    # Share of the model's volume that may be thinner than the minimum before
    # the check reports a warning (tiny tips and edges are always slightly thin).
    thin_volume_warn_fraction: float = field(default_factory=lambda: _env_float("DNT_THIN_WARN_FRACTION", 0.01))

    # Loose fragments smaller than this share of the largest part are treated as
    # AI noise and removed. Anything bigger is kept and reported to the student.
    debris_volume_fraction: float = field(default_factory=lambda: _env_float("DNT_DEBRIS_FRACTION", 0.005))

    # Flat base options.
    base_plinth_height_mm: float = field(default_factory=lambda: _env_float("DNT_BASE_HEIGHT_MM", 2.0))
    base_plinth_margin_mm: float = field(default_factory=lambda: _env_float("DNT_BASE_MARGIN_MM", 1.0))
    base_flatten_depth_fraction: float = field(default_factory=lambda: _env_float("DNT_FLATTEN_FRACTION", 0.03))

    # Which axis of the AI model's output points "up". TripoSR is believed to be
    # Z-up; this must be confirmed on the GPU machine in Phase 1.
    triposr_up_axis: str = field(default_factory=lambda: os.getenv("DNT_TRIPOSR_UP_AXIS", "z").strip().lower())

    # AI models students may use. Others stay switched off even if installed,
    # until their licences have been checked for classroom use (see MODEL_LICENCES.md).
    allowed_models: Tuple[str, ...] = field(default_factory=lambda: _env_list("DNT_ALLOWED_MODELS", ("triposr",)))

    # Development mode: no AI model is loaded; uploads are answered with the
    # pre-made sample meshes in sample-data/meshes. Everything after the AI step
    # (scaling, base, checks, export) still runs for real.
    dev_mode: bool = field(default_factory=lambda: _env_bool("DNT_DEV_MODE", False))

    # Uploads.
    max_upload_mb: float = field(default_factory=lambda: _env_float("DNT_MAX_UPLOAD_MB", 15.0))
    allowed_upload_ext: Tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")

    @property
    def max_box_mm(self) -> Tuple[float, float, float]:
        return (self.max_x_mm, self.max_y_mm, self.max_z_mm)


def get_settings() -> DntSettings:
    """Read settings fresh (so tests and the CLI can change env vars)."""
    return DntSettings()
