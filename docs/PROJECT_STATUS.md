# Project status

What has been built, what was tested where, and what still needs your devices. Updated each stage.

Legend: ✅ done and tested automatically · 🧪 built, awaiting a test on your device · ⏳ not started

## Stages

| Stage | Status | Evidence |
|---|---|---|
| 1. Audit Phase 0/1 | ✅ | All Phase 0/1 tests still pass; findings below |
| 2. Cross-device demo (web app, 3D viewer, adjustments, downloads) | ✅ automated / 🧪 real iPad Safari | 38 Python tests, 69 browser checks (Chromium, desktop and iPad-sized) |
| 3. Lenovo CPU support + Windows guide | 🧪 | CPU mode built; `docs/WINDOWS_CPU_SETUP.md`; **not run on Windows yet** |
| 4. Real AI test on the Lenovo | ⏳ waiting for you | `scripts/cpu_test.py` ready; dry-run checked with samples only |
| 5. iPad ↔ Lenovo over local Wi-Fi | 🧪 | Access code + launchers built (needed to test Stage 2 on the iPad); `docs/IPAD_LOCAL_NETWORK.md` |
| 6. Cloudflare-ready front end | ⏳ | Groundwork only: relative paths, `config.js` backend address, CORS off by default |

## Stage 1 audit: what was already working

- TripoSR integration code is in place (`backend/app.py`, `run_triposr`). **It has never been run in
  this project**, because no machine with the model has run it yet.
- Print preparation, sample models, STL/3MF export, checks and the dev-mode tests all passed.
- Problems found and fixed in Stage 2:
  - The original page had no 3D viewer, only a flat preview picture.
  - Downloads had no proper file names.
  - Several AI jobs could run at once (would run out of memory on a 16 GB laptop).
  - A hidden fallback in `/convert` could have answered with a sample model. It is now an error.
  - The server listened on all networks with no protection. It now listens only on the
    laptop itself unless started "for iPad", and then needs an access code.

## Not verified yet (needs your devices)

- Real TripoSR generation on CPU: speed, memory, and whether the shapes look like the designs.
- Which way TripoSR's models face ("up" and "front"). The setting `DNT_TRIPOSR_UP_AXIS` fixes "up".
- Real iPad Safari behaviour: touch gestures, camera, HEIC photos, saving to Files.
- Opening the downloaded files in Bambu Studio.

## Known limitations

- **Design fidelity:** TripoSR builds a 3D shape from one picture and has to invent the back.
  Pencil line drawings may produce flat or blobby shapes. This is the main risk, and Stage 4 measures it.
- Adjustments are rotation, size (30-100% of the largest that fits) and base. Freeform editing
  (e.g. thickening an arm) is a future feature.
- The model always sits centred on the print plate. "Reposition" is done by turning or tipping it.
- The rotation preview is instant but approximate. The exact print file follows within a few
  seconds, and downloads are locked until it is ready.
- One shared access code. There are no student or teacher accounts yet (teacher approval is a later stage).
- Jobs are kept in memory: restarting the server clears them.
