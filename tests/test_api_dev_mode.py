"""End-to-end API test in development mode (no GPU, no AI model)."""
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DNT_DEV_MODE", "1")
    from fastapi.testclient import TestClient
    import app as app_module
    with TestClient(app_module.app) as c:
        yield c


def wait_done(client, job_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"/status/{job_id}").json()
        if st["status"] in {"done", "error", "cancelled"}:
            return st
        time.sleep(0.3)
    raise AssertionError("job did not finish")


def upload(client, name, **params):
    data = (ROOT / "sample-data/sketches" / name).read_bytes()
    return client.post("/convert", params=params, files={"file": (name, data, "image/png")})


def test_health_reports_dev_mode(client):
    h = client.get("/health").json()
    assert h["dev_mode"] is True
    assert h["max_box_mm"] == [40.0, 40.0, 60.0]
    assert "trellis2_endpoint_enabled" not in h and "hf_token_present" not in h


def test_owl_sketch_to_stl(client):
    r = upload(client, "owl.png", base="plinth")
    assert r.status_code == 200, r.text
    st = wait_done(client, r.json()["job_id"])
    assert st["status"] == "done", st["message"]
    assert "not an AI result" in st["message"]
    assert st["print_report"]["overall"] == "pass"
    assert st["print_report"]["base_applied"] == "plinth"
    stl = client.get(st["stl_url"])
    tmf = client.get(st["tmf_url"])
    assert stl.status_code == 200 and len(stl.content) > 10_000
    assert tmf.status_code == 200 and tmf.content[:2] == b"PK"


def test_robot_sample_reports_problems(client):
    st = wait_done(client, upload(client, "robot.png").json()["job_id"])
    ids = {c["id"]: c["status"] for c in st["print_report"]["checks"]}
    assert ids["parts"] == "warn" and ids["thickness"] == "warn"


def test_rejects_bad_inputs(client):
    data = b"not really"
    assert client.post("/convert", files={"file": ("x.exe", data, "image/png")}).status_code == 400
    assert client.post("/convert", files={"file": ("x.png", data, "text/plain")}).status_code == 400
    assert client.post("/convert", params={"base": "tower"},
                       files={"file": ("x.png", data, "image/png")}).status_code == 400


def test_upload_size_limit(client, monkeypatch):
    monkeypatch.setenv("DNT_MAX_UPLOAD_MB", "0.001")
    big = b"\0" * 5000
    assert client.post("/convert", files={"file": ("x.png", big, "image/png")}).status_code == 413
