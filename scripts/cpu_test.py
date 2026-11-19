"""
CPU test workflow for the Lenovo (Stage 4).

Runs the real TripoSR engine on up to four test images, one at a time, and writes a
results table you can send back:

    venv\\Scripts\\python.exe scripts\\cpu_test.py

Put your own pictures in the folder  my-test-images\\  with these names (JPG or PNG):

    coloured.jpg   a coloured, shaded hand-drawn figurine design
    pencil.jpg     a black-and-white pencil sketch
    product.jpg    a photo of a real object (e.g. a toy or clay model)

The owl sample sketch is always tested first. Missing pictures are skipped.
Do not use photos of people, names or anything private: use fictional designs.

Results go to  test-results\\cpu-<date-time>\\  (results.md, results.json, and one
folder of 3D files per picture). The table separates two questions:

  1. Did the code run?            (measured automatically)
  2. Does the 3D model look like the design?  (YOU judge this; fill in the last columns)
"""
import argparse
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sketch_to_stl as s2s  # noqa: E402

ROOT = s2s.ROOT
TEST_SET = [
    ("owl sample sketch", ROOT / "sample-data" / "sketches" / "owl.png"),
    ("coloured hand-drawn design", "coloured"),
    ("black-and-white pencil sketch", "pencil"),
    ("photo of a physical product", "product"),
]


def find_image(stem: str, folder: Path):
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG"):
        p = folder / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def system_info():
    info = {"os": platform.platform(), "python": platform.python_version(), "cpu": platform.processor()}
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / 1024 ** 3, 1)
        info["cpu_cores"] = f"{psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads"
    except ImportError:
        pass
    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        info["torch_threads"] = torch.get_num_threads()
    except ImportError:
        pass
    return info


def fmt(v):
    return "–" if v is None else str(v)


def main():
    ap = argparse.ArgumentParser(description="Run the real TripoSR CPU test set")
    ap.add_argument("--images", default=str(ROOT / "my-test-images"), help="folder with coloured/pencil/product pictures")
    ap.add_argument("--device", default="cpu", choices=["cpu", "auto", "cuda", "mps"])
    ap.add_argument("--resolution", type=int, default=256)
    ap.add_argument("--base", default="plinth", choices=["none", "flatten", "plinth"])
    ap.add_argument("--dev", action="store_true", help="dry run with sample meshes (checks the workflow, NOT the AI)")
    args = ap.parse_args()

    folder = Path(args.images)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_root = ROOT / "test-results" / f"{'dev' if args.dev else 'cpu'}-{stamp}"
    out_root.mkdir(parents=True, exist_ok=True)

    plan = []
    for label, src in TEST_SET:
        path = src if isinstance(src, Path) else find_image(src, folder)
        plan.append((label, path))
    print("Test pictures:")
    for label, path in plan:
        print(f"  {label:32} {path if path else '(not found - skipped)'}")

    print()
    with s2s.PeakMemory() as load_mem:
        try:
            app, load_s = s2s.load_engine(args.dev, args.device)
        except Exception as e:
            print(f"FAILED to start the engine: {e}")
            return 3
    print(f"Model loading took {load_s} s (peak RAM so far {load_mem.peak_gb} GB)\n")

    rows = []
    for i, (label, path) in enumerate(plan, start=1):
        if not path:
            rows.append({"label": label, "image": None, "status": "skipped"})
            continue
        print(f"--- {i}/{len(plan)}: {label} ({path.name}) ---")
        t0 = time.time()
        try:
            m = s2s.run_one(app, path, out_root / f"{i}-{path.stem}", args.dev, args.base, args.resolution)
        except Exception as e:  # keep going with the other pictures
            m = {"image": path.name, "status": "error", "message": str(e), "total_s": round(time.time() - t0, 1)}
        m["label"] = label
        rows.append(m)
        if m.get("status") == "done":
            s2s.print_result(m)
        else:
            print(f"FAILED: {m.get('message')}")
        print()

    info = system_info()
    info["model_load_s"] = load_s
    info["peak_ram_during_load_gb"] = load_mem.peak_gb
    (out_root / "results.json").write_text(json.dumps({"system": info, "results": rows}, indent=2, default=str))

    lines = [
        f"# CPU test results ({stamp})",
        "",
        f"**Mode:** {'DEVELOPMENT DRY RUN - sample meshes, NOT AI' if args.dev else 'Real AI (TripoSR) on ' + args.device.upper()}",
        "",
        "## Computer",
        "",
    ] + [f"- {k}: {v}" for k, v in info.items()] + [
        "",
        "## 1. Did the code run? (measured automatically)",
        "",
        "| Picture | Ran OK | Total (s) | AI inference (s) | Mesh extraction (s) | Clean-up (s) | Print prep (s) | Peak RAM (GB) | STL | 3MF | Watertight | Manifold | Parts | Thickness | Size (mm) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r.get("status") == "skipped":
            lines.append(f"| {r['label']} | skipped (no picture) |" + " |" * 13)
            continue
        size = " × ".join(str(v) for v in (r.get("size_mm") or [])) or "–"
        lines.append(
            f"| {r['label']} | {'yes' if r.get('status') == 'done' else 'NO: ' + str(r.get('message'))[:60]} | "
            f"{fmt(r.get('total_s'))} | {fmt(r.get('ai_inference_s'))} | {fmt(r.get('mesh_extraction_s'))} | "
            f"{fmt(r.get('cleanup_s'))} | {fmt(r.get('print_prep_s'))} | {fmt(r.get('peak_ram_gb'))} | "
            f"{'yes' if r.get('stl_ok') else 'no'} | {'yes' if r.get('3mf_ok') else 'no'} | {fmt(r.get('watertight'))} | "
            f"{fmt(r.get('manifold'))} | {fmt(r.get('parts'))} | {fmt(r.get('thickness'))} | {size} |")
    lines += [
        "",
        f"Model loading (once, before the first picture): {load_s} s",
        "",
        "## 2. Does the 3D model look like the design? (fill in by hand)",
        "",
        "Open each `model.stl` (in the numbered folders here) in Bambu Studio or the web app viewer,",
        "and compare it with the picture. Score 1 (nothing like it) to 5 (very close).",
        "",
        "| Picture | Silhouette / outline (1-5) | Proportions (1-5) | Distinctive features kept? | Stands upright? | Back side sensible? | Notes |",
        "|---|---|---|---|---|---|---|",
    ] + [f"| {r['label']} |  |  |  |  |  |  |" for r in rows if r.get("status") != "skipped"] + [
        "",
        "A run can succeed in part 1 (code worked, file is printable) and still fail in part 2",
        "(the shape does not match the design). Both matter.",
    ]
    md = out_root / "results.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Results written to: {md}")
    print("Please fill in part 2 of results.md, then send results.md (and the screenshots if you like).")
    if args.dev:
        print("Reminder: this was a DRY RUN with sample meshes. It does not test the AI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
