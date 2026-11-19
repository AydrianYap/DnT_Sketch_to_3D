"""
Phase 1 prototype: turn one sketch or photo into a print-ready STL and 3MF.

It runs the same code the web app uses (backend/app.py), without the web server:

    image -> background removal -> TripoSR -> mesh clean-up
          -> fit to 40 x 40 x 60 mm -> optional flat base -> checks -> STL + 3MF

Real AI run (needs the PIXFORM install with TripoSR, ideally on an NVIDIA GPU):

    python scripts/sketch_to_stl.py sample-data/sketches/owl.png --out my_owl

Development mode (no GPU, no AI; uses a pre-made sample mesh so you can test
the sizing, base and checks):

    python scripts/sketch_to_stl.py sample-data/sketches/robot.png --out test --dev

Exit code: 0 = print checks passed, 1 = warnings, 2 = a check failed, 3 = error.
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


def parse_args():
    ap = argparse.ArgumentParser(description="Sketch or photo -> print-ready STL/3MF")
    ap.add_argument("image", help="PNG/JPG/WEBP of the sketch or photo")
    ap.add_argument("--out", default="output", help="folder to write model.stl, model.3mf and the report")
    ap.add_argument("--dev", action="store_true", help="development mode: sample mesh instead of AI")
    ap.add_argument("--base", choices=["none", "flatten", "plinth"], default="none",
                    help="flat base: none, flatten (slice bottom flat) or plinth (add a round base)")
    ap.add_argument("--resolution", type=int, default=256, help="TripoSR mesh resolution (128-1024)")
    ap.add_argument("--post", choices=["none", "light", "standard", "heavy"], default="standard",
                    help="mesh clean-up level")
    ap.add_argument("--keep-background", action="store_true",
                    help="skip AI background removal (use if the image already has a transparent background)")
    return ap.parse_args()


def main():
    args = parse_args()
    image = Path(args.image).resolve()
    if not image.exists():
        print(f"Image not found: {image}")
        return 3

    start_dir = Path.cwd()
    if args.dev:
        os.environ["DNT_DEV_MODE"] = "1"
    else:
        os.environ.setdefault("PIXFORM_ACTIVE_MODELS", "triposr")

    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    import app  # noqa: E402  (PIXFORM backend; importing does not load models)

    if not args.dev:
        print("Loading TripoSR and background remover (first run downloads ~1-2 GB of weights)...")
        app.load_all_models()
        if app.models.get("triposr") is None:
            health = app.model_health.get("triposr", {})
            print(f"TripoSR is not available: {health.get('status')} {health.get('error') or ''}")
            print("Install it with install.ps1 / install_mac.sh, or use --dev to test without AI.")
            return 3
        print(f"Device: {app.models.get('runtime_device')}")

    job_id = str(uuid.uuid4())
    upload = app.UPLOAD_DIR / f"{job_id}{image.suffix.lower()}"
    shutil.copyfile(image, upload)  # the pipeline deletes its upload copy when done
    out_dir = app.OUTPUT_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    app.jobs[job_id] = dict(
        job_id=job_id, status="queued", progress=0, message="Queued...", model_used="",
        time_taken=None, stl_url=None, tmf_url=None, glb_url=None, obj_url=None,
        preview_url=None, poly_count=None, cancel_requested=False, delete_requested=False,
        stage="queued", last_update_ts=time.time(), created_at=time.time(), completed_at=None,
        cleanup_after_ts=None, upload_path=str(upload), output_dir=str(out_dir),
        upload_deleted=False, base_mode=args.base, print_report=None, report_url=None,
    )
    settings = {
        "remove_bg": not args.keep_background,
        "resolution": app._normalize_triposr_resolution(args.resolution),
        "steps": 50,
        "post": args.post,
        "preserve_proportions": False,
        "source_name": image.name,
    }
    runner = app.run_demo if args.dev else app.run_triposr
    print(f"Running {'development mode (sample mesh, no AI)' if args.dev else 'TripoSR'} on {image.name} ...")
    asyncio.run(runner(job_id, upload, out_dir, settings))

    job = app.jobs[job_id]
    if job["status"] != "done":
        print(f"FAILED: {job.get('message')}")
        return 3

    dest = Path(args.out)
    if not dest.is_absolute():
        dest = start_dir / dest
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("model.stl", "model.3mf", "model.glb", "preview.png", "print_report.json"):
        src = out_dir / name
        if src.exists():
            shutil.copyfile(src, dest / name)
    shutil.rmtree(out_dir, ignore_errors=True)

    report = job.get("print_report") or {}
    print()
    print(f"Result: {job.get('message')}")
    print(f"Model:  {job.get('model_used')}   time: {job.get('time_taken')} s")
    print(f"Size:   {' x '.join(str(v) for v in report.get('size_mm', []))} mm   "
          f"volume: {report.get('volume_cm3')} cm3   base: {report.get('base_applied')}")
    print()
    marks = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skipped": "SKIP", "info": "INFO"}
    for c in report.get("checks", []):
        print(f"  [{marks.get(c['status'], c['status'])}] {c['label']}: {c['message']}")
    for note in report.get("notes", []):
        print(f"  note: {note}")
    print()
    print(f"Files written to {dest}:")
    for f in sorted(dest.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size // 1024} KB)")
    if args.dev:
        print("\nReminder: development mode used a pre-made sample mesh. This is NOT an AI result.")
    return {"pass": 0, "warn": 1, "fail": 2}.get(report.get("overall"), 3)


if __name__ == "__main__":
    sys.exit(main())
