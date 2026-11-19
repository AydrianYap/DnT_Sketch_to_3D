# Testing

There are two kinds of tests:

- **Automated tests** run by a command. They need no GPU and no AI model.
- **Manual tests** can only be done on your real devices (the Lenovo and the iPad).
  They cannot be automated, because they need real Safari, real touch, real Bambu Studio
  and the real AI model.

## Running the automated tests

On the Lenovo, in PowerShell in the app folder:

```powershell
.\venv\Scripts\python.exe -m pip install pytest httpx
.\venv\Scripts\python.exe -m pytest tests
```

Browser tests (optional; they need Node.js from <https://nodejs.org>):

```powershell
npm install playwright
npx playwright install chromium
node tests\browser\run_browser_tests.mjs
```

The browser test starts its own demo server and saves screenshots in `tests\browser\output\`.

## What the automated tests cover

| Area | Test file | Notes |
|---|---|---|
| Scaling to 40 × 40 × 60 mm, proportions kept | `tests/test_print_prep.py` | many shapes, incl. tiny and huge |
| Flat base and plinth | `tests/test_print_prep.py`, `tests/test_api_stage2.py` | stays in the box, stays closed, flat bottom |
| Watertight, manifold, separate parts, thickness | `tests/test_print_prep.py` | deliberately broken meshes |
| Image upload validation (type, size, not-a-picture) | `tests/test_api_dev_mode.py`, `tests/test_api_stage2.py` | |
| STL and 3MF export, millimetre units | `tests/test_api_stage2.py` | |
| Model dimension accuracy (report = STL = 3MF = viewer) | `tests/test_api_stage2.py`, browser test | |
| Adjustments: size, rotation, base, undo | `tests/test_api_stage2.py`, browser test | |
| Error handling: AI missing or crashing → clear error, **never** a sample | `tests/test_api_stage2.py` | simulated failure, not real TripoSR |
| One AI job at a time | `tests/test_api_stage2.py` | |
| Backend availability (`/health`), demo vs AI mode flags | `tests/test_api_dev_mode.py`, `tests/test_api_stage2.py` | |
| Access code for iPad testing | `tests/test_api_stage2.py`, browser test | |
| Viewer loads and draws a **solid surface** (not dots) | browser test | measures how much of the viewer is model-coloured |
| Six view buttons, wireframe, reset | browser test | |
| Desktop and iPad-sized screens, light and dark | browser test | **Chromium imitating an iPad, not real Safari** |

## Manual checks: Lenovo (Windows)

| # | Check | Result |
|---|---|---|
| L1 | `install.ps1 -Profile cpu -Models triposr` finishes without `[ERROR]` | |
| L2 | `Start-Demo.bat` opens the app; owl sample generates; STL downloads | |
| L3 | `Start-AI.bat`: label shows **AI mode · TripoSR on CPU** | |
| L4 | `scripts\cpu_test.py` completes; `results.md` filled in (part 1 automatic, part 2 by you) | |
| L5 | Peak RAM stays below ~14 GB (laptop does not freeze) | |
| L6 | Real AI models **stand upright** in the viewer (if lying down, see below) | |
| L7 | The **Front** button shows the side that faced the camera in the sketch | |
| L8 | A downloaded 3MF opens in Bambu Studio at the size shown in the app | |
| L9 | Chrome and Edge both work | |

If AI models lie on their back or side (L6), try each of these in PowerShell before
starting, and note which works:
`$env:DNT_TRIPOSR_UP_AXIS = 'y'` then `.\scripts\windows\start.bat ai local`
(other values to try: `-y`, `x`, `-x`).

## Manual checks: iPad Pro (Safari)

Use `Start-Demo-for-iPad.bat` first (see [IPAD_LOCAL_NETWORK.md](IPAD_LOCAL_NETWORK.md)).

| # | Check | Result |
|---|---|---|
| P1 | Page opens over Wi-Fi; access code accepted | |
| P2 | **Take a photo** opens the camera; the photo appears in the editor | |
| P3 | **Choose a picture** from Photos (HEIC photo) and from Files (PNG) both work | |
| P4 | Crop corners can be dragged with a finger **and** with Apple Pencil | |
| P5 | Rotate, brightness and contrast change the preview | |
| P6 | Replace and Delete picture work | |
| P7 | 3D viewer: **one finger rotates, pinch zooms, two fingers pan**, smoothly | |
| P8 | Page itself does not zoom or scroll while using the viewer | |
| P9 | Front/Back/Left/Right/Top/Bottom/Fit/Reset/Wireframe buttons work | |
| P10 | Size slider, Turn, Tip over, Base, Undo/Redo work; downloads wait until "up to date" | |
| P11 | **Download 3MF** → Safari asks to download → file appears in **Files → Downloads** | |
| P12 | The file name is the figurine name (e.g. `Ollie-the-Owl.3mf`) | |
| P13 | Portrait and landscape both look right; text is easy to read | |
| P14 | Dark mode (Settings → Display) looks right | |
| P15 | With `Start-AI-for-iPad.bat`: an iPad photo of a sketch becomes an AI model | |

Send the filled-in tables (or just the failures with a screenshot) and I will fix them.
