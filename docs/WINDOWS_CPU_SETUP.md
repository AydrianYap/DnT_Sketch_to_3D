# Windows setup (Lenovo laptop, no NVIDIA graphics card)

This guide installs D&T Sketch-to-3D on a Windows 11 laptop and runs the AI
(TripoSR) on the **CPU** (the main processor). No programming knowledge is needed:
copy each command exactly.

**Time:** about 1 hour the first time (mostly waiting for downloads).
**Disk space:** about 10 GB free.
**Internet:** needed for installing and for the first AI start (it downloads about
2 GB of AI model files). Home Wi-Fi is best: school networks sometimes block these downloads.

> **About your Lenovo's chips.** The AI runs on the Ryzen CPU. The Radeon 860M graphics
> and the Ryzen AI NPU are **not used**: TripoSR needs NVIDIA (CUDA) or Apple graphics
> for acceleration, and AMD's alternatives (ROCm, DirectML, the NPU) are not supported
> by this AI model. CPU mode is slower, but it works the same way.

---

## Step 1 - Install Git

Git downloads the app's code from GitHub and keeps it up to date.

1. Go to <https://git-scm.com/download/win> and download **64-bit Git for Windows Setup**.
2. Run it and click **Next** on every page (the default choices are fine), then **Install**.

## Step 2 - Install Python 3.10

The app needs **Python 3.10** exactly (newer versions do not work with all the AI parts).

1. Go to <https://www.python.org/downloads/release/python-31011/>.
2. Scroll to **Files** and click **Windows installer (64-bit)**.
3. Run it. On the first screen, **tick "Add python.exe to PATH"**, then click **Install Now**.
4. When it says "Setup was successful", click **Close**.

## Step 3 - Download the app

1. Click the **Start** button, type `PowerShell`, and open **Windows PowerShell**.
2. Copy and paste these lines (right-click pastes in PowerShell), pressing **Enter** after each:

   ```powershell
   mkdir C:\DnT
   cd C:\DnT
   git clone https://github.com/AydrianYap/DnT_Sketch_to_3D.git
   cd DnT_Sketch_to_3D
   git checkout claude/sleepy-hypatia-nrsn4e
   ```

   - The repository is private, so a GitHub sign-in window opens the first time. Sign in
     with your GitHub account and click **Authorize**.
   - `C:\DnT` is used on purpose: avoid Desktop/Documents folders that OneDrive syncs,
     because syncing thousands of AI files causes errors.

3. Check that Python and Git work:

   ```powershell
   py -3.10 --version
   git --version
   ```

   You should see `Python 3.10.11` and a Git version. If not, see **Troubleshooting**.

## Step 4 - Install

Still in PowerShell, in `C:\DnT\DnT_Sketch_to_3D`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1 -Profile cpu -Models triposr
```

- The first line allows the installer to run in this window only (it does not change
  your computer's security settings permanently).
- The installer creates a private Python folder called `venv`, installs PyTorch (CPU
  version), the 3D tools and TripoSR. This takes **15-40 minutes**. Lots of text scrolls
  past. That is normal.
- It finishes with a green success message. If it stops with a red `[ERROR]`, copy the
  last 20 lines and see **Troubleshooting**.

### If the AI part will not install

You can still test everything except the AI (demo mode) with a lighter install:

```powershell
py -3.10 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r backend\requirements-dnt.txt
```

## Step 5 - Try demo mode (no AI, 1 minute)

In File Explorer, open `C:\DnT\DnT_Sketch_to_3D` and **double-click `Start-Demo.bat`**.

- A black window opens (the server). Keep it open.
- After a few seconds your browser opens <http://localhost:8000>.
- The purple **Demo mode** label means you will see sample models (owl or robot), not
  models made from your sketch.
- Try: **Try a sample: Owl** → **Make my 3D model** → rotate the model, change the size,
  choose a base, download the STL.

**Windows says "Windows protected your PC"?** Click **More info** → **Run anyway**. This
appears for downloaded `.bat` files.

**To stop:** click the black window and press **Ctrl + C**, then type **Y** and press Enter
if asked "Terminate batch job". Or simply close the black window.

## Step 6 - Try the real AI on the laptop

Double-click **`Start-AI.bat`**.

- The first start downloads the TripoSR model (about 1.7 GB) and the background remover
  (about 170 MB). Wait until the black window shows `Application startup complete`.
- The top-right label should say **AI mode · TripoSR on CPU**.
- Upload a sketch and click **Make my 3D model**. On a CPU this can take several minutes.
  Do not close the window while it works.
- Only one picture is processed at a time. If two are sent, the second waits in line.

## Step 7 - Run the CPU test set (Stage 4)

This measures speed and memory for four test pictures and writes a results table.

1. Create the folder `C:\DnT\DnT_Sketch_to_3D\my-test-images`.
2. Put in up to three of your own **fictional, non-personal** pictures, named exactly:
   - `coloured.jpg`: a coloured, shaded hand-drawn figurine design
   - `pencil.jpg`: a black-and-white pencil sketch
   - `product.jpg`: a photo of a real object (a toy, a clay model)
3. Close any running Start-*.bat windows. Then in PowerShell:

   ```powershell
   cd C:\DnT\DnT_Sketch_to_3D
   .\venv\Scripts\python.exe scripts\cpu_test.py
   ```

4. When it finishes, it prints where the results are, e.g.
   `test-results\cpu-20261120-1530\results.md`. Open that file in Notepad, fill in
   part 2 (does each model look like the design?), and send it back. The numbered folders
   next to it contain each `model.stl`, which you can open in Bambu Studio.

The owl sample is always included, so the test works even before you add your own pictures.

## Updating to the newest version later

```powershell
cd C:\DnT\DnT_Sketch_to_3D
git pull
```

If the update notes say new packages were added, run the Step 4 install again.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| `py is not recognized` or `Python 3.10 not found` | Re-run the Python 3.10 installer, choose **Modify**, and make sure **py launcher** and **Add Python to environment variables** are ticked. Close and reopen PowerShell. |
| `git is not recognized` | Install Git (Step 1), then close and reopen PowerShell. |
| `running scripts is disabled on this system` | You skipped the `Set-ExecutionPolicy -Scope Process ...` line. Run it, then the installer again, in the same window. |
| `[ERROR] The app is not installed yet` when double-clicking a Start file | Step 4 has not finished successfully. Run it again. |
| Installer fails while downloading (`timed out`, `connection reset`) | Use home Wi-Fi rather than school Wi-Fi, then run the installer again. It starts over safely. |
| `Microsoft Visual C++ 14.0 or greater is required` | One package had to be built from source. Copy the package name from the error and send it to me. Usually a different version fixes it. Demo mode (lighter install) still works meanwhile. |
| Window says `TripoSR failed to load` or the label says **AI engine not ready** | The model download failed. Check the internet connection and restart `Start-AI.bat`. Hugging Face (huggingface.co) must not be blocked. |
| `address already in use` / `error while attempting to bind on address` | The app is already running in another window. Close all black server windows and try again. |
| The browser shows "This site can't be reached" | The black window was closed or has not finished starting. Wait for `Application startup complete`, then refresh. |
| AI is extremely slow or the laptop freezes | Close other programs (especially browser tabs). The app already uses CPU-friendly settings (resolution 256). If it still runs out of memory, set fewer threads: in PowerShell run `$env:DNT_CPU_THREADS = '4'` and then `.\scripts\windows\start.bat ai local`. |
| Antivirus warns about `python.exe` | It is the Python you installed in Step 2. Allow it. |

If something else goes wrong, copy the last 30 lines of the black window (right-click the
title bar → **Edit** → **Select All**, then Enter to copy) and send them.
