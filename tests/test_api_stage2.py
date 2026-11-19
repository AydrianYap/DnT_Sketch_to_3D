"""Stage 2/3 backend tests: adjustments, downloads, access code, queue, real-mode errors.

No GPU or AI model is needed. "Real AI mode" tests check behaviour when the model is
missing or fails; they do NOT test actual TripoSR generation.
"""
import asyncio
import io
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest
import trimesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

OWL = (ROOT / "sample-data/sketches/owl.png").read_bytes()


def wait_done(client, job_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"/status/{job_id}").json()
        if st["status"] in {"done", "error", "cancelled"}:
            return st
        time.sleep(0.2)
    raise AssertionError("job did not finish")


@pytest.fixture()
def demo(monkeypatch):
    monkeypatch.setenv("DNT_DEV_MODE", "1")
    monkeypatch.delenv("DNT_ACCESS_CODE", raising=False)
    from fastapi.testclient import TestClient
    import app as app_module
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture()
def real_mode(monkeypatch):
    """Real AI mode without any model installed (load step skipped)."""
    monkeypatch.delenv("DNT_DEV_MODE", raising=False)
    monkeypatch.delenv("DNT_ACCESS_CODE", raising=False)
    from fastapi.testclient import TestClient
    import app as app_module
    monkeypatch.setattr(app_module, "load_all_models", lambda: None)
    monkeypatch.setitem(app_module.models, "triposr", None)
    with TestClient(app_module.app) as c:
        yield c, app_module


def make_job(client, base="none"):
    r = client.post("/convert", params={"base": base}, files={"file": ("owl.png", OWL, "image/png")})
    assert r.status_code == 200, r.text
    st = wait_done(client, r.json()["job_id"])
    assert st["status"] == "done", st["message"]
    return st


def stl_extents(content: bytes):
    m = trimesh.load(io.BytesIO(content), file_type="stl", force="mesh")
    return np.round(m.extents, 2), m


# ---------------------------------------------------------------- app & files

def test_root_redirects_to_student_app(demo):
    r = demo.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/app/"
    page = demo.get("/app/")
    assert page.status_code == 200 and "D&amp;T Sketch-to-3D" in page.text
    for asset in ("app/styles.css", "app/js/app.js", "app/js/viewer.js", "app/vendor/three.module.min.js"):
        assert demo.get("/" + asset).status_code == 200, asset
    assert demo.get("/pixform").status_code == 200  # original PIXFORM page still available


def test_job_reports_sample_and_source_image(demo):
    st = make_job(demo)
    assert st["is_sample"] is True
    assert st["source_image_url"]
    assert demo.get(st["source_image_url"]).headers["content-type"].startswith("image/jpeg")
    stages = [s for s, _ in st["stage_log"]]
    assert "print_prep" in stages and stages[-1] == "done"


def test_download_names_and_types(demo):
    st = make_job(demo)
    r = demo.get(f"/download/{st['job_id']}/stl", params={"name": "Ollie the Owl!"})
    assert r.status_code == 200
    assert 'filename="Ollie-the-Owl.stl"' in r.headers["content-disposition"]
    assert r.headers["content-type"].startswith("model/stl")
    r3 = demo.get(f"/download/{st['job_id']}/3mf")
    z = zipfile.ZipFile(io.BytesIO(r3.content))
    model_xml = z.read([n for n in z.namelist() if n.endswith(".model")][0]).decode()
    assert 'unit="millimeter"' in model_xml
    assert demo.get(f"/download/{st['job_id']}/exe").status_code == 404
    assert demo.get("/download/nope/stl").status_code == 404


def test_exported_stl_and_3mf_match_report_dimensions(demo):
    st = make_job(demo, base="plinth")
    ext, mesh = stl_extents(demo.get(f"/download/{st['job_id']}/stl").content)
    assert np.allclose(ext, st["print_report"]["size_mm"], atol=0.02)
    assert mesh.is_watertight
    m3 = trimesh.load(io.BytesIO(demo.get(f"/download/{st['job_id']}/3mf").content), file_type="3mf", force="mesh")
    assert np.allclose(m3.extents, ext, atol=0.02)


# ---------------------------------------------------------------- adjustments

def test_adjust_size_rotation_base_and_undo(demo):
    st = make_job(demo)
    jid = st["job_id"]
    full, _ = stl_extents(demo.get(f"/download/{jid}/stl").content)

    half = demo.post(f"/jobs/{jid}/adjust", json={"size_percent": 50, "base": "none"}).json()
    ext, _ = stl_extents(demo.get(f"/download/{jid}/stl").content)
    assert np.allclose(ext, full / 2, atol=0.1)
    assert half["revision"] == 1 and half["adjustments"]["size_percent"] == 50

    lay = demo.post(f"/jobs/{jid}/adjust", json={"rotate_x": 90, "size_percent": 100}).json()
    ext, _ = stl_extents(demo.get(f"/download/{jid}/stl").content)
    assert ext[1] > ext[2]  # lying down: long side is now depth
    assert lay["print_report"]["checks"][0]["status"] == "pass"

    based = demo.post(f"/jobs/{jid}/adjust", json={"base": "plinth"}).json()
    assert based["print_report"]["base_applied"] == "plinth"

    # "Undo" in the browser re-sends an earlier state: result must match the original.
    demo.post(f"/jobs/{jid}/adjust", json={"base": "none"})
    ext, _ = stl_extents(demo.get(f"/download/{jid}/stl").content)
    assert np.allclose(ext, full, atol=0.05)


@pytest.mark.parametrize("body,code", [
    ({"size_percent": 5}, 400), ({"size_percent": 150}, 400),
    ({"base": "tower"}, 400), ({"rotate_z": 999}, 400),
])
def test_adjust_rejects_bad_values(demo, body, code):
    st = make_job(demo)
    assert demo.post(f"/jobs/{st['job_id']}/adjust", json=body).status_code == code


def test_adjust_unknown_job(demo):
    assert demo.post("/jobs/missing/adjust", json={}).status_code == 404


# ---------------------------------------------------------------- uploads & errors

def test_rejects_non_picture_with_image_extension(demo):
    r = demo.post("/convert", files={"file": ("fake.png", b"this is text", "image/png")})
    assert r.status_code == 400 and "could not be opened" in r.json()["detail"]


def test_real_mode_without_model_gives_clear_error_not_sample(real_mode):
    client, app_module = real_mode
    h = client.get("/health").json()
    assert h["dev_mode"] is False and h["triposr"] is False
    r = client.post("/convert", files={"file": ("owl.png", OWL, "image/png")})
    assert r.status_code == 503
    assert "TripoSR" in r.json()["detail"]


def test_real_mode_ai_failure_reports_error_not_sample(real_mode):
    client, app_module = real_mode

    class Broken:
        def __call__(self, *a, **k):
            raise RuntimeError("simulated AI crash")

    app_module.models["triposr"] = Broken()
    try:
        r = client.post("/convert", params={"remove_bg": "false"},
                        files={"file": ("owl.png", OWL, "image/png")})
        assert r.status_code == 200
        st = wait_done(client, r.json()["job_id"])
        assert st["status"] == "error"
        assert st["is_sample"] is False
        assert st["stl_url"] is None
    finally:
        app_module.models["triposr"] = None


def test_disallowed_model_rejected(real_mode):
    client, _ = real_mode
    r = client.post("/convert", params={"model": "hunyuan"}, files={"file": ("owl.png", OWL, "image/png")})
    assert r.status_code == 403


# ---------------------------------------------------------------- one job at a time

def test_ai_jobs_run_one_at_a_time(demo, monkeypatch):
    import app as app_module
    running = {"now": 0, "max": 0}

    async def fake_runner(job_id, image_path, out_dir, settings):
        running["now"] += 1
        running["max"] = max(running["max"], running["now"])
        app_module.upd(job_id, status="processing", stage="inference")
        await asyncio.sleep(0.5)
        running["now"] -= 1
        app_module.upd(job_id, status="done", progress=100, stage="done")

    monkeypatch.setattr(app_module, "run_demo", fake_runner)
    ids = [demo.post("/convert", files={"file": (f"o{i}.png", OWL, "image/png")}).json()["job_id"] for i in range(3)]
    for jid in ids:
        assert wait_done(demo, jid)["status"] == "done"
    assert running["max"] == 1


# ---------------------------------------------------------------- access code

def test_access_code_required_when_set(monkeypatch):
    monkeypatch.setenv("DNT_DEV_MODE", "1")
    monkeypatch.setenv("DNT_ACCESS_CODE", "AB12CD")
    from fastapi.testclient import TestClient
    import app as app_module
    with TestClient(app_module.app) as c:
        assert c.get("/health").json()["access_code_required"] is True
        assert c.get("/app/").status_code == 200           # page loads so the code can be typed
        r = c.post("/convert", files={"file": ("owl.png", OWL, "image/png")})
        assert r.status_code == 401 and r.json()["code"] == "access_code_required"
        assert c.get("/outputs/anything/model.stl").status_code == 401
        assert c.post("/auth", json={"code": "WRONG1"}).status_code == 401
        assert c.post("/auth", json={"code": "ab12cd"}).status_code == 200  # case-insensitive, sets cookie
        st = make_job(c)
        assert st["status"] == "done"
    # header works too (for a separately hosted page)
    with TestClient(app_module.app) as c2:
        r = c2.get("/status/none", headers={"X-Access-Code": "AB12CD"})
        assert r.status_code == 404


def test_no_cross_site_access_by_default(demo):
    r = demo.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
