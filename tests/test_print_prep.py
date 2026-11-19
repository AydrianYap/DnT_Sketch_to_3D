"""Tests for the classroom print preparation (no GPU needed)."""
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dnt.config import DntSettings  # noqa: E402
from dnt.print_prep import fit_to_box, orient_up, prepare_for_print, run_checks  # noqa: E402

BOX = (40.0, 40.0, 60.0)


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


@pytest.mark.parametrize("extents", [(10, 10, 10), (200, 20, 20), (5, 300, 7), (1, 1, 1000), (0.3, 0.2, 0.1)])
def test_fit_keeps_proportions_and_fits(extents):
    m = trimesh.creation.box(extents=extents)
    out, scale = fit_to_box(m, BOX)
    assert np.all(out.extents <= np.array(BOX) + 1e-6)
    # at least one side touches the limit (largest model that fits)
    assert np.isclose(np.max(out.extents / np.array(BOX)), 1.0)
    # proportions unchanged
    assert np.allclose(out.extents / out.extents.max(), np.array(extents) / max(extents))
    # stands on the floor, centred
    assert np.isclose(out.bounds[0][2], 0.0)
    assert np.allclose((out.bounds[0][:2] + out.bounds[1][:2]) / 2, 0.0)


def test_orient_y_up_to_z_up():
    m = trimesh.creation.box(extents=(1, 5, 2))  # tall along Y
    out = orient_up(m, "y")
    assert np.isclose(out.extents[2], 5.0)


@pytest.mark.parametrize("mode", ["none", "flatten", "plinth"])
def test_base_modes_stay_in_box_and_closed(mode):
    m = trimesh.creation.icosphere(subdivisions=3)
    m.apply_scale([1, 1, 2])
    out, report = prepare_for_print(m, base_mode=mode)
    assert report["base_applied"] == mode
    assert np.all(out.extents <= np.array(BOX) + 0.01)
    assert out.is_watertight
    assert report["overall"] == "pass"
    if mode != "none":
        # flat bottom: a big face area sits at z = 0
        bottom = np.abs(out.triangles_center[:, 2]) < 1e-3
        assert out.area_faces[bottom].sum() > 20.0


def test_open_mesh_fails_watertight_and_skips_thickness():
    m = trimesh.creation.box(extents=(10, 10, 10))
    m.update_faces(np.arange(len(m.faces) - 2))  # remove one square face -> hole
    report = run_checks(fit_to_box(m, BOX)[0])
    c = by_id(report)
    assert c["watertight"]["status"] == "fail"
    assert c["thickness"]["status"] == "skipped"
    assert report["overall"] == "fail"


def test_non_manifold_edge_detected():
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = a.copy()
    b.apply_translation([10, 10, 0])  # two cubes sharing only one edge
    merged = trimesh.util.concatenate([a, b])
    merged.merge_vertices()
    assert by_id(run_checks(merged))["manifold"]["status"] == "fail"


def test_separate_parts_reported_not_deleted():
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.creation.icosphere(radius=2)
    b.apply_translation([15, 0, 0])
    out, report = prepare_for_print(trimesh.util.concatenate([a, b]))
    assert by_id(report)["parts"]["status"] == "warn"
    assert by_id(report)["parts"]["parts"] == 2


def test_tiny_debris_removed():
    a = trimesh.creation.box(extents=(10, 10, 10))
    speck = trimesh.creation.icosphere(radius=0.05)
    speck.apply_translation([20, 0, 0])
    out, report = prepare_for_print(trimesh.util.concatenate([a, speck]))
    assert by_id(report)["parts"]["status"] == "pass"
    assert by_id(report)["parts"]["debris_removed"] == 1


def test_thin_feature_warns_and_thick_model_passes():
    body = trimesh.creation.box(extents=(20, 20, 20))
    pin = trimesh.creation.cylinder(radius=0.3, height=15)
    pin.apply_translation([0, 0, 17])
    thin = trimesh.boolean.union([body, pin], engine="manifold")
    _, report = prepare_for_print(thin)
    t = by_id(report)["thickness"]
    assert t["status"] == "warn"
    assert t["thin_regions"] and t["thin_regions"][0]["z_from_mm"] > 30

    _, report = prepare_for_print(trimesh.creation.box(extents=(20, 20, 30)))
    assert by_id(report)["thickness"]["status"] == "pass"


def test_custom_box_from_settings(monkeypatch):
    monkeypatch.setenv("DNT_MAX_Z_MM", "30")
    s = DntSettings()
    out, report = prepare_for_print(trimesh.creation.box(extents=(1, 1, 5)), settings=s)
    assert np.isclose(out.extents[2], 30.0)


def test_sample_meshes_behave_as_documented():
    owl = trimesh.load(ROOT / "sample-data/meshes/owl.stl", force="mesh")
    robot = trimesh.load(ROOT / "sample-data/meshes/robot.stl", force="mesh")
    _, r_owl = prepare_for_print(owl)
    _, r_robot = prepare_for_print(robot)
    assert r_owl["overall"] == "pass"
    c = by_id(r_robot)
    assert c["parts"]["status"] == "warn"
    assert c["thickness"]["status"] == "warn"
