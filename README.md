# D&T Sketch-to-3D

An educational adaptation of [PIXFORM](https://github.com/dmonfrooij/pixform) for a
Secondary 2 Design & Technology figurine project: students turn a sketch or photo into
a small 3D-printable figurine (max **40 x 40 x 60 mm**). The AI runs **locally** on a
school GPU machine; no student images are sent to outside AI services, and there are
no paid APIs or credits. See [`NOTICE.md`](NOTICE.md) for attribution and
[`MODEL_LICENCES.md`](MODEL_LICENCES.md) for model licences.

**Status:** see [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md). The web app, 3D viewer and
print preparation are tested automatically in demo mode. **Real AI generation has not yet been
tested** on the Lenovo or any other machine.

### Start here (Windows laptop, no NVIDIA GPU)

1. Install: [`docs/WINDOWS_CPU_SETUP.md`](docs/WINDOWS_CPU_SETUP.md)
2. Double-click one of these in the app folder:

   | File | What it does |
   |---|---|
   | `Start-Demo.bat` | Demo mode (sample models, no AI) on this laptop |
   | `Start-AI.bat` | Real AI (TripoSR on the CPU) on this laptop |
   | `Start-Demo-for-iPad.bat` | Demo mode, open on the iPad over Wi-Fi (shows an access code) |
   | `Start-AI-for-iPad.bat` | Real AI on the laptop, used from the iPad |

3. iPad over Wi-Fi: [`docs/IPAD_LOCAL_NETWORK.md`](docs/IPAD_LOCAL_NETWORK.md)
4. Tests (automatic and manual checklists): [`docs/TESTING.md`](docs/TESTING.md)

### What is added on top of PIXFORM

- Every model is scaled uniformly (proportions kept) to fit inside 40 x 40 x 60 mm.
- Optional flat base: `flatten` (slice the bottom flat) or `plinth` (add a round base, counted inside the 60 mm).
- Print checks with student-friendly messages: size, closed surface (watertight),
  clean geometry (manifold), separate pieces, and an estimate of parts thinner than 1.2 mm.
  The results are saved as `print_report.json` and returned by `/status/{job_id}` as `print_report`.
- Separate parts are reported instead of silently deleted. Only tiny AI noise is removed.
- Only approved models load (`DNT_ALLOWED_MODELS`, default `triposr`).
- The remote TRELLIS.2 endpoint mode was removed.
- Uploads are limited to JPG/PNG/WEBP up to 15 MB.

### Try it without a GPU (development mode)

```bash
pip install -r backend/requirements-dnt.txt
python scripts/make_samples.py            # only needed if sample-data/ is missing
python scripts/sketch_to_stl.py sample-data/sketches/owl.png --out test_owl --dev --base plinth
python -m pytest tests
```

Development mode skips the AI step and uses pre-made sample meshes
(`sample-data/meshes/owl.stl` passes all checks; `robot.stl` deliberately has a loose
part and a thin antenna). Everything after the AI step is the real code. To run the web
server in development mode: `cd backend && DNT_DEV_MODE=1 python app.py`, then
`POST /convert` with an image and optional `base=none|flatten|plinth`.
The student interface is at `/app/` (the address `/` redirects there); the original PIXFORM
page is still available at `/pixform`.

### Settings

All classroom limits live in `backend/dnt/config.py` and can be set by environment variables:
`DNT_MAX_X_MM`, `DNT_MAX_Y_MM`, `DNT_MAX_Z_MM`, `DNT_MIN_THICKNESS_MM` (default 1.2),
`DNT_BASE_HEIGHT_MM`, `DNT_ALLOWED_MODELS`, `DNT_DEV_MODE`, `DNT_MAX_UPLOAD_MB`,
`DNT_TRIPOSR_UP_AXIS`, `DNT_HOST` (127.0.0.1 = this computer only; 0.0.0.0 = local network,
requires an access code), `DNT_PORT`, `DNT_ACCESS_CODE`, `DNT_CPU_THREADS`, `DNT_CPU_MAX_RESOLUTION`
(default 256), `DNT_ALLOWED_ORIGINS` (for a separately hosted front end; empty by default).

---

*The original PIXFORM documentation follows.*

# PIXFORM - Image to 3D

PIXFORM converts a single image into a local 3D model with focus on maximum output quality, usable exports, and easy local installation.

Four generation modes are available in this repository:

- **TripoSR** - fastest option, works on `cuda`, `mps` and `cpu`
- **Hunyuan3D-2** - higher shape quality, currently only on `cuda`
- **TRELLIS** - highest quality, with GLB export and textured GLB where possible, only on `cuda`
- **TRELLIS.2** - next-generation TRELLIS variant with improved geometry and texture, only on `cuda`

**Export formats:** `STL`, `3MF`, `GLB`, `OBJ`

---

## What PIXFORM does

- local webapp on `http://localhost:8000`
- upload single image
- optional AI background removal
- choice of fast, quality or maximum quality
- preview render of result
- download multiple 3D formats

The backend runs from `backend/app.py` and the web interface is in `frontend/index.html`.

---

## Supported Platforms

### Windows + NVIDIA
Recommended for best performance and access to all models.

Supported via:
- `install.ps1` (PowerShell installer)
- `PIXFORM.bat` (launcher)

### macOS / MacBook Pro (Apple Silicon)
Suitable for fast local workflow with `mps` / Metal.

Supported via:
- `install_mac.sh` (bash installer)
- `PIXFORM.sh` (launcher)

### CPU fallback
Also works without supported GPU, but clearly slower. In that case, especially **TripoSR** is practically usable.

---

## Requirements

### General
- Git
- Python **3.10**

### Windows
- Windows 10 or 11
- PowerShell
- For best performance: NVIDIA GPU with recent driver

For CUDA profiles (`-Profile nvidia`) additional requirements apply:

- NVIDIA driver + `nvidia-smi` available
- Visual Studio Build Tools (C++ toolchain, `cl.exe`) for native builds
- CUDA Toolkit with `nvcc` available on `PATH`
- Recommended: toolkit version matching the CUDA version of installed PyTorch (default in this script: `12.4`)

### macOS
- `python3` available
- macOS shell with bash
- Apple Silicon implicitly supported via `mps`

> Both Windows and macOS installers expect **Python 3.10** explicitly.

---

## Models

| Model | Best for | Device support | Notes |
|---|---|---|---|
| TripoSR | Quick testing, previews, broader compatibility | CUDA / MPS / CPU | Loads as primary general fallback |
| Hunyuan3D-2 | Better geometry than TripoSR | CUDA | Only loaded if runtime device is `cuda` |
| TRELLIS | Highest quality | CUDA | Attempts textured GLB; otherwise falls back to plain GLB |
| TRELLIS.2 | Next-gen quality with improved geometry and texture | CUDA | Uses `trellis2` runtime; requires `trellis2` install selection |

The backend chooses the runtime device via `PIXFORM_DEVICE` with safe fallback logic.

---

## Device Choice

PIXFORM supports these device modes:

- `cuda`
- `mps`
- `cpu`
- `auto`

The backend's device resolution order in `backend/app.py` is:

1. `cuda`
2. `mps`
3. `cpu`

Alias names that also work:
- `nvidia` -> `cuda`
- `mac` -> `mps`

If a requested device is unavailable, PIXFORM automatically falls back to a usable alternative.

---

## Installation

Use preferably a clean virtual environment; the installation scripts create their own `venv`.

### Windows

Run in PowerShell:

```powershell
cd C:\Users\YourUsername\path\to\pixform
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1 -Profile auto
```

`install.ps1` now asks which models you want to install. Press Enter for all models, or pass them explicitly:

```powershell
.\install.ps1 -Profile nvidia -Models triposr,trellis
.\install.ps1 -Profile auto -Models 1,2
```

For `-Profile nvidia` you can pre-set the toolkit in the current shell (example for CUDA 12.4):

```powershell
$env:CUDA_HOME = 'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4'
$env:CUDA_PATH = $env:CUDA_HOME
$env:Path = "$env:CUDA_HOME\bin;$env:CUDA_HOME\libnvvp;$env:Path"
nvcc --version
```

Then verify which CUDA version PyTorch in the venv uses:

```powershell
.\venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda)"
```

If `torch.version.cuda` and `nvcc --version` don't match, optional native builds (like `nvdiffrast` and `o-voxel` for TRELLIS.2) may be skipped.

Available profiles for `install.ps1`:

- `auto` - uses `cuda` if NVIDIA available, otherwise `cpu`
- `nvidia` - forces CUDA installation and installs CUDA-only model support
- `cpu` - installs CPU-only runtime

Model selection values for `install.ps1 -Models`:

- `all`
- `triposr`, `hunyuan`, `trellis`, `trellis2`
- numeric shortcuts: `1=triposr`, `2=hunyuan`, `3=trellis`, `4=trellis2`

What `install.ps1` does:

- recreates `venv`
- installs PyTorch 2.5.1 with CUDA 12.4 support
- installs core packages (FastAPI, rembg, OpenCV, trimesh)
- clones only the selected model repos
- clones **TRELLIS** / **TRELLIS.2** only when selected and CUDA is available
- patches TRELLIS for kaolin-free operation
- writes chosen runtime device to `.pixform_device`
- writes selected model state to `.pixform_models.json`

### macOS / MacBook Pro

Run:

```bash
cd /path/to/pixform
chmod +x install_mac.sh PIXFORM.sh
./install_mac.sh mac
```

Available profiles for `install_mac.sh`:

- `mac` - uses `mps`
- `auto` - also chooses `mps` on macOS
- `cpu` - forces CPU
- `nvidia` - CUDA profile for systems where explicitly desired

What `install_mac.sh` does:

- recreates `venv`
- installs PyTorch 2.5.1
- installs core dependencies
- installs `open3d` best-effort
- clones and patches **TripoSR**
- clones **Hunyuan3D-2** and **TRELLIS** only in CUDA profile
- writes runtime device to `.pixform_device`

### First Start

On the first real run, model weights may need additional downloads and local caching. This takes time and disk space, especially for Hunyuan3D-2 and TRELLIS.

---

## Starting

### Windows

```bat
PIXFORM.bat
```

Optional overrides:

```bat
PIXFORM.bat nvidia
PIXFORM.bat cpu
PIXFORM.bat mac
PIXFORM.bat mps
```

Or with environment variable:

```powershell
$env:PIXFORM_DEVICE = 'cuda'
.\PIXFORM.bat
```

### macOS

```bash
./PIXFORM.sh
```

Optional overrides:

```bash
./PIXFORM.sh mac
./PIXFORM.sh mps
./PIXFORM.sh cpu
./PIXFORM.sh nvidia
```

Or with environment variable:

```bash
PIXFORM_DEVICE=mps ./PIXFORM.sh
```

The launcher starts `backend/app.py` and then opens the browser at:

```text
http://localhost:8000
```

---

## Manual Device Override

You can also set the environment variable directly.

### Windows PowerShell

```powershell
$env:PIXFORM_DEVICE = 'cuda'
.\PIXFORM.bat
```

```powershell
$env:PIXFORM_DEVICE = 'cpu'
.\PIXFORM.bat
```

### macOS / bash

```bash
PIXFORM_DEVICE=mps ./PIXFORM.sh
```

```bash
PIXFORM_DEVICE=cpu ./PIXFORM.sh
```

The launchers otherwise automatically read `.pixform_device`; if that file doesn't exist, they use `auto`.

---

## Usage in the App

Basic workflow:

1. Drag or select an image
2. Choose a model
3. Choose a quality preset
4. Choose whether background removal is needed
5. Click **Generate**
6. Download `STL`, `3MF`, `GLB` or `OBJ`

You can press **Stop** while a job is running. Cancellation is best-effort: the current internal stage is allowed to finish safely, then the job moves to `cancelled`.

The job card now also shows a stage heartbeat (`stage` + last update age), so you can see which internal phase is active during long TRELLIS runs.

The backend has these routes for this:

- `GET /health` - model status, device info
- `POST /convert` - submit image for 3D generation (model: `triposr`, `hunyuan`, `trellis`, `trellis2`)
- `GET /status/{job_id}` - poll job status
- `POST /jobs/{job_id}/cancel` - request safe cancellation
- `DELETE /jobs/{job_id}` - cancel/delete job
- `POST /jobs/cleanup` - prune old completed jobs (`?all=true` to force cleanup of all terminal jobs)

---

## Quality Presets

The presets come directly from the UI in `frontend/index.html`.

| Preset | TripoSR resolution | Hunyuan/TRELLIS steps | Post-processing | Approx time (TripoSR / Hunyuan / TRELLIS) |
|---|---:|---:|---|---|
| Draft | 128 | 10 | `none` | ~10 sec / ~1 min / ~3 min |
| Low | 192 | 20 | `light` | ~30 sec / ~2 min / ~4 min |
| Medium | 256 | 30 | `light` | ~1 min / ~3 min / ~5 min |
| High | 512 | 50 | `standard` | ~3 min / ~5 min / ~8 min |
| Ultra | 640 | 75 | `standard` | ~5 min / ~8 min / ~10 min |
| Extreme | 768 | 100 | `heavy` | ~8 min / ~12 min / ~12 min |
| Maximum | 1024 | 100 | `heavy` | ~12+ min / ~15 min / ~15 min |
| Custom | manual | manual | manual | depends on settings |

Available post-processing levels:

- `none` - no post-processing
- `light` - basic cleanup and smoothing
- `standard` - full repair + smoothing + Poisson reconstruction
- `heavy` - aggressive refinement with voxel remesh fallback

---

## Best 3D Quality: Recommended Choices

For best possible output:

- Use a sharp, well-lit image
- Keep subject fully in frame
- Use one clear object
- Avoid busy backgrounds and motion blur
- Prefer `Hunyuan3D-2` or `TRELLIS` on NVIDIA/CUDA
- Choose `High`, `Ultra`, `Extreme` or `Maximum`
- Keep post-processing on `standard` or `heavy`

Practical choice per situation:

- **Quick testing** -> TripoSR + Draft/Low/Medium
- **Good mesh quality** -> Hunyuan3D-2 + High/Ultra
- **Best possible quality** -> TRELLIS + High/Ultra/Extreme
- **Next-gen quality** -> TRELLIS.2 + High/Ultra/Extreme (CUDA only, requires trellis2 install)

---

## Output Formats

PIXFORM exports these formats from the backend:

- `model.stl`
- `model.3mf`
- `model.glb`
- `model.obj`
- `preview.png`

Important:

- `STL` is the most 3D-printer-friendly export
- `3MF` is also offered and has a manual fallback export in the backend
- `OBJ` is broadly compatible
- `GLB` is available for compact distribution and preview
- With **TRELLIS**, PIXFORM attempts a **textured GLB**; if optional dependencies fail, a plain mesh GLB is written instead

Outputs are stored in:

```text
backend/outputs/<job-id>/
```

Uploads go to:

```text
backend/uploads/
```

---

## Model Availability and `/health`

The `GET /health` endpoint returns, among others:

- whether `triposr` is loaded
- whether `hunyuan` is loaded
- whether `trellis` is loaded
- whether `trellis2` is loaded
- whether `rembg` is active
- whether `cuda` or `mps` is available
- which runtime device is actually used
- per-model `*_status` and `*_error` fields (e.g. `trellis2_status`, `trellis2_error`)

This is useful if a CUDA-only model is not selectable or doesn't load correctly at startup.

---

## Troubleshooting

### 1. CUDA model doesn't load
Check:
- NVIDIA driver
- whether `torch.cuda.is_available()` is true
- whether you installed with `-Profile nvidia`
- whether `backend/trellis` and `backend/hy3dgen` exist

### 2. On Mac the app doesn't use MPS
Check:
- whether `PIXFORM_DEVICE` is not set to `cpu`
- whether `.pixform_device` doesn't accidentally contain `cpu`
- whether PyTorch sees `mps`

### 3. TRELLIS doesn't provide textured GLB
This is not always a hard error. The backend has explicit fallback logic:
- first attempt textured GLB
- then fallback to plain GLB export

### 4. TRELLIS won't load on Windows
Check:
- run installation with `-Profile nvidia`
- check `/health` for `trellis_status` and `trellis_error`
- use `xformers` as attention backend (backend sets this by default on Windows)

Extra context:
- a notice about missing `triton` is usually a performance warning and not necessarily a load failure
- the `kaolin` import in `flexicubes.py` has a fallback in this codebase

### 5. Installation takes a long time
This is normal for:
- PyTorch
- Hunyuan3D-2 dependencies
- TRELLIS dependencies
- first model download at runtime

### 6. TRELLIS can run long before finishing
TRELLIS post-processing can be heavy. PIXFORM now uses conservative timeout defaults and safe fallback behavior.

Optional tuning via environment variables:

- `PIXFORM_TRELLIS_POST_TIMEOUT_SEC` (default depends on post level)
- `PIXFORM_TRELLIS_TEXTURE_TIMEOUT_SEC` (default `480`)
- `PIXFORM_TRELLIS_TEXTURED=1` to enable textured GLB attempt (default is off)

### 7. TRELLIS.2 fails with "gated repo" or "401 Unauthorized"

TRELLIS.2 uses `facebook/dinov3-vitl16-pretrain-lvd1689m` as its image encoder. This model is hosted as a restricted download on HuggingFace. You only need to deal with this **once** — after the one-time download it runs fully locally with no internet or authentication required.

#### One-time download

1. Go to https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m and click **Request access** (approved within minutes)
2. Create a token at https://huggingface.co/settings/tokens
3. Run the included download script:

   ```powershell
   # Windows PowerShell
   $env:HF_TOKEN = 'hf_your_token_here'
   .\venv\Scripts\python.exe download_dinov3.py
   ```

   ```bash
   # macOS
   HF_TOKEN=hf_your_token_here ./venv/bin/python download_dinov3.py
   ```

4. The model is saved to `backend/models/dinov3_vitl16/`

**After this, start PIXFORM normally — no token, no internet, runs fully offline.**

> The download is ~1 GB and happens only once. The script tells you exactly what to do if something goes wrong.

### 8. TRELLIS.2 endpoint-first mode (removed)

The original PIXFORM could send images to a remote TRELLIS.2 endpoint before falling back
to local generation. This was removed in D&T Sketch-to-3D so student images never
leave the local machine. `PIXFORM_TRELLIS2_ENDPOINT_URL` is ignored.

---

## Project Structure

```text
pixform/
|-- backend/
|   |-- app.py            # FastAPI backend and model pipelines
|   |-- outputs/          # generated results
|   |-- uploads/          # uploaded source images
|   |-- tsr/              # TripoSR runtime files
|   |-- hy3dgen/          # Hunyuan3D runtime files
|   |-- trellis/          # TRELLIS runtime files (after CUDA install)
|   `-- trellis2/         # TRELLIS.2 runtime files (after CUDA install with trellis2 selected)
|-- frontend/
|   `-- index.html        # web interface
|-- install.ps1           # Windows installer
|-- install_mac.sh        # macOS installer
|-- download_dinov3.py    # one-time DINOv3 encoder download for TRELLIS.2 (run once, then fully offline)
|-- PIXFORM.bat           # Windows launcher
|-- PIXFORM.sh            # macOS launcher
|-- pixform.iss           # Inno Setup script
|-- triposr_repo/         # cloned source during/after install
|-- hunyuan3d_repo/       # cloned source during/after install
|-- trellis_repo/         # cloned source during/after CUDA install
|-- trellis2_official_repo/ # cloned source during/after CUDA install with trellis2
`-- README.md
```

---

## Windows Installer Build

Based on the repository, there's an Inno Setup script in `pixform.iss`.

General process:

1. Install Inno Setup
2. Open `pixform.iss`
3. Build the script

---

## Fixes in This Version

- Fixed TRELLIS kaolin import with fallback for flexicubes
- Improved install script with better error handling
- Fixed app.py UTF-16 encoding issue
- Better TRELLIS dependency validation
- Clearer error messages in `/health` endpoint
- Updated README with complete setup instructions
- Added TRELLIS.2 support (`trellis2` model)
- Added `download_dinov3.py` for one-time offline setup of the DINOv3 encoder required by TRELLIS.2
- TRELLIS.2 DINOv3 encoder now auto-detected from `backend/models/dinov3_vitl16/` — fully offline after first download

---

## Credits

- [TripoSR](https://github.com/VAST-AI-Research/TripoSR)
- [Hunyuan3D-2](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)
- [TRELLIS](https://github.com/microsoft/TRELLIS)
- [rembg](https://github.com/danielgatis/rembg)
- [Open3D](http://www.open3d.org/)

## License

See `LICENSE`.

