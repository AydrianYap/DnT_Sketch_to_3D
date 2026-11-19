> **Lenovo / CPU users:** follow [WINDOWS_CPU_SETUP.md](WINDOWS_CPU_SETUP.md) instead. This page is for a machine with an NVIDIA GPU.

# Phase 1 test on the GPU machine

Goal: prove the real AI engine turns **one sketch into a printable STL** at the
right size. Until this test has been run and recorded, AI generation is
**untested** in this adaptation. Development mode only uses pre-made samples.

## 1. Install (once)

Windows with an NVIDIA GPU (PowerShell, in the repository folder):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1 -Profile nvidia -Models triposr
```

macOS (Apple Silicon):

```bash
./install_mac.sh mac
```

The first real run downloads the TripoSR weights (about 1.7 GB) from Hugging Face
and the background-removal weights from GitHub. After that it can run offline.

## 2. Check without AI first (1 minute)

Windows:

```powershell
.\venv\Scripts\python.exe scripts\sketch_to_stl.py sample-data\sketches\owl.png --out test_dev --dev --base plinth
```

macOS:

```bash
./venv/bin/python scripts/sketch_to_stl.py sample-data/sketches/owl.png --out test_dev --dev --base plinth
```

Expected: all checks `PASS`, files in `test_dev/`. This proves the sizing, base,
checks and export work on that machine.

## 3. Real AI run

```powershell
.\venv\Scripts\python.exe scripts\sketch_to_stl.py sample-data\sketches\owl.png --out test_ai_owl
```

Then repeat with **your own** test images, ideally:

1. a coloured, shaded drawing of one figurine on plain paper (photographed on an iPad)
2. a plain pencil line drawing
3. a photo of a clay or card model

Options: `--base flatten` or `--base plinth`, `--resolution 512` (more detail,
slower), `--post light` (keeps more detail, may be less closed).

## 4. What to check and record

Open each `model.stl` in your slicer (e.g. Bambu Studio, PrusaSlicer, Cura):

| Check | Record |
|---|---|
| Did the run finish? How long did it take? | |
| GPU name and VRAM (printed at start) | |
| Does the figurine **stand upright**? | If it lies on its back or side, re-run with `DNT_TRIPOSR_UP_AXIS=y` (or `-y`, `x`) and note which one is right. |
| Does the slicer show 40 x 40 x 60 mm or smaller? | |
| Does the slicer report errors or repairs? | |
| Does the shape look like the drawing (front, side, back)? | |
| Report results (PASS / WARN / FAIL lines) | |

Setting the up-axis on Windows for one run:

```powershell
$env:DNT_TRIPOSR_UP_AXIS = 'y'
.\venv\Scripts\python.exe scripts\sketch_to_stl.py sample-data\sketches\owl.png --out test_ai_owl_y
```

Send back the table plus the printed output, and Phase 2 can be built on known results.

## Exit codes

`0` all checks passed, `1` warnings, `2` a check failed, `3` the run failed.
