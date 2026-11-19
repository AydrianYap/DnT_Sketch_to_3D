"""
Turn one sketch or photo into a print-ready STL and 3MF (no web server needed).

It runs the same code the web app uses (backend/app.py):

    image -> background removal -> TripoSR -> mesh clean-up
          -> fit to 40 x 40 x 60 mm -> optional flat base -> checks -> STL + 3MF

Real AI run on a laptop without an NVIDIA GPU (Windows):

    venv\\Scripts\\python.exe scripts\\sketch_to_stl.py sample-data\\sketches\\owl.png --out test_owl --device cpu

Development mode (no AI; uses a pre-made sample mesh to test sizing, base and checks):

    python scripts/sketch_to_stl.py sample-data/sketches/robot.png --out test --dev

It prints the time for each stage and the peak memory (RAM) used.
Exit code: 0 = print checks passed, 1 = warnings, 2 = a check failed, 3 = error.
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


class PeakMemory:
    """Samples this program's memory use (RAM) in the background and keeps the highest value."""

    def __init__(self, interval=0.25):
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        try:
            import psutil
            self._proc = psutil.Process()
        except ImportError:
            self._proc = None

    def __enter__(self):
        if self._proc:
            self.peak = self._proc.memory_info().rss
            self._t = threading.Thread(target=self._run, daemon=True)
            self._t.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            try:
                self.peak = max(self.peak, self._proc.memory_info().rss)
            except Exception:
                pass
            self._stop.wait(self.interval)

    def __exit__(self, *exc):
        self._stop.set()

    @property
    def peak_gb(self):
        return round(self.peak / 1024 ** 3, 2) if self._proc else None


def stage_durations(stage_log):
    """[(stage, start_ts), ...] -> {stage: seconds} using the next stage's start as the end."""
    out = {}
    for (name, t0), (_, t1) in zip(stage_log, stage_log[1:]):
        out[name] = round(out.get(name, 0.0) + (t1 - t0), 1)
    return out


def load_engine(dev: bool, device: str = "auto"):
    """Import the PIXFORM backend and load TripoSR (or nothing in dev mode). Returns (app, seconds)."""
    if dev:
        os.environ["DNT_DEV_MODE"] = "1"
    else:
        os.environ.pop("DNT_DEV_MODE", None)
        os.environ.setdefault("PIXFORM_ACTIVE_MODELS", "triposr")
        if device and device != "auto":
            os.environ["PIXFORM_DEVICE"] = device
    os.chdir(BACKEND)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    import app  # noqa: E402  (importing does not load models)

    t0 = time.time()
    if not dev:
        print("Loading TripoSR and the background remover...")
        print("(The very first time, this downloads about 2 GB. Later runs load from disk.)")
        app.load_all_models()
        if app.models.get("triposr") is None:
            health = app.model_health.get("triposr", {})
            raise RuntimeError(f"TripoSR is not available: {health.get('status')} {health.get('error') or ''}. "
                               "See docs/WINDOWS_CPU_SETUP.md, or use --dev to test without AI.")
        print(f"Device: {app.models.get('runtime_device')}")
    return app, round(time.time() - t0, 1)


def run_one(app, image: Path, dest: Path, dev: bool, base="none", resolution=256, post="standard",
            remove_bg=True) -> dict:
    """Run one image through the pipeline, copy results to dest, return a metrics dict."""
    job_id = str(uuid.uuid4())
    upload = app.UPLOAD_DIR / f"{job_id}{image.suffix.lower()}"
    shutil.copyfile(image, upload)  # the pipeline deletes its own upload copy when done
    out_dir = app.OUTPUT_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    app.jobs[job_id] = dict(
        job_id=job_id, status="queued", progress=0, message="Queued...", model_used="",
        time_taken=None, stl_url=None, tmf_url=None, glb_url=None, obj_url=None,
        preview_url=None, poly_count=None, cancel_requested=False, delete_requested=False,
        stage="queued", last_update_ts=time.time(), created_at=time.time(), completed_at=None,
        cleanup_after_ts=None, upload_path=str(upload), output_dir=str(out_dir),
        upload_deleted=False, base_mode=base, print_report=None, report_url=None,
        is_sample=dev, stage_log=[["queued", time.time()]],
    )
    settings = {
        "remove_bg": remove_bg,
        "resolution": app._normalize_triposr_resolution(resolution),
        "steps": 50,
        "post": post,
        "preserve_proportions": False,
        "source_name": image.name,
    }
    runner = app.run_demo if dev else app.run_triposr
    t0 = time.time()
    with PeakMemory() as mem:
        asyncio.run(runner(job_id, upload, out_dir, settings))
    total = round(time.time() - t0, 1)
    job = app.jobs[job_id]
    log = list(job.get("stage_log") or [])
    log.append(["end", time.time()])
    stages = stage_durations(log)

    dest.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in ("model.stl", "model.3mf", "model.glb", "preview.png", "print_report.json"):
        src = out_dir / name
        if src.exists():
            shutil.copyfile(src, dest / name)
            files[name] = (dest / name).stat().st_size
    shutil.rmtree(out_dir, ignore_errors=True)

    report = job.get("print_report") or {}
    checks = {c["id"]: c["status"] for c in report.get("checks", [])}
    return {
        "image": image.name,
        "mode": "development (sample mesh, NOT AI)" if dev else f"AI: {job.get('model_used')}",
        "status": job["status"],
        "message": job.get("message"),
        "total_s": total,
        "stages_s": stages,
        "ai_inference_s": stages.get("inference"),
        "mesh_extraction_s": round(stages.get("mesh_extract", 0) + stages.get("mesh_ready", 0), 1) or None,
        "cleanup_s": stages.get("postprocess"),
        "print_prep_s": stages.get("print_prep"),
        "peak_ram_gb": mem.peak_gb,
        "stl_ok": "model.stl" in files,
        "3mf_ok": "model.3mf" in files,
        "watertight": checks.get("watertight"),
        "manifold": checks.get("manifold"),
        "parts": checks.get("parts"),
        "thickness": checks.get("thickness"),
        "overall": report.get("overall"),
        "size_mm": report.get("size_mm"),
        "out_dir": str(dest),
        "report": report,
    }


def print_result(m: dict):
    print()
    print(f"Result:  {m['message']}")
    print(f"Mode:    {m['mode']}")
    print(f"Time:    total {m['total_s']} s   " + "   ".join(f"{k} {v} s" for k, v in m["stages_s"].items()))
    if m["peak_ram_gb"] is not None:
        print(f"Memory:  peak {m['peak_ram_gb']} GB RAM")
    rep = m["report"]
    if rep:
        print(f"Size:    {' x '.join(str(v) for v in rep.get('size_mm', []))} mm   volume: {rep.get('volume_cm3')} cm3"
              f"   base: {rep.get('base_applied')}")
        marks = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skipped": "SKIP", "info": "INFO"}
        for c in rep.get("checks", []):
            print(f"  [{marks.get(c['status'], c['status'])}] {c['label']}: {c['message']}")
        for note in rep.get("notes", []):
            print(f"  note: {note}")
    print(f"Files:   {m['out_dir']}")


def parse_args():
    ap = argparse.ArgumentParser(description="Sketch or photo -> print-ready STL/3MF")
    ap.add_argument("image", help="PNG/JPG/WEBP of the sketch or photo")
    ap.add_argument("--out", default="output", help="folder to write model.stl, model.3mf and the report")
    ap.add_argument("--dev", action="store_true", help="development mode: sample mesh instead of AI")
    ap.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto",
                    help="where the AI runs: cpu for a laptop without an NVIDIA GPU")
    ap.add_argument("--base", choices=["none", "flatten", "plinth"], default="none",
                    help="flat base: none, flatten (slice bottom flat) or plinth (add a round base)")
    ap.add_argument("--resolution", type=int, default=256, help="TripoSR mesh detail (128-1024). 256 suits a CPU")
    ap.add_argument("--post", choices=["none", "light", "standard", "heavy"], default="standard",
                    help="mesh clean-up level")
    ap.add_argument("--keep-background", action="store_true",
                    help="skip AI background removal (only if the image already has a transparent background)")
    ap.add_argument("--metrics-json", help="also save the measurements to this JSON file")
    return ap.parse_args()


def main():
    args = parse_args()
    start_dir = Path.cwd()
    image = Path(args.image).resolve()
    if not image.exists():
        print(f"Image not found: {image}")
        return 3
    dest = Path(args.out)
    if not dest.is_absolute():
        dest = start_dir / dest
    try:
        with PeakMemory() as load_mem:
            app, load_s = load_engine(args.dev, args.device)
    except Exception as e:
        print(f"FAILED to start the engine: {e}")
        return 3
    print(f"Running {'development mode (sample mesh, no AI)' if args.dev else 'TripoSR'} on {image.name} ...")
    m = run_one(app, image, dest, args.dev, args.base, args.resolution, args.post, not args.keep_background)
    m["model_load_s"] = load_s
    m["peak_ram_gb"] = max(filter(None, [m["peak_ram_gb"], load_mem.peak_gb]), default=None)
    print(f"\nModel loading: {load_s} s")
    if m["status"] != "done":
        print(f"FAILED: {m['message']}")
        if args.metrics_json:
            Path(args.metrics_json).write_text(json.dumps(m, indent=2, default=str))
        return 3
    print_result(m)
    if args.metrics_json:
        Path(args.metrics_json).write_text(json.dumps(m, indent=2, default=str))
    if args.dev:
        print("\nReminder: development mode used a pre-made sample mesh. This is NOT an AI result.")
    return {"pass": 0, "warn": 1, "fail": 2}.get(m.get("overall"), 3)


if __name__ == "__main__":
    sys.exit(main())
