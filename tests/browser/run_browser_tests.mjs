// Automated browser test of the student interface in demo mode.
//
//   node tests/browser/run_browser_tests.mjs            (starts its own demo server)
//   DNT_TEST_URL=http://localhost:8000 node tests/browser/run_browser_tests.mjs
//
// Needs Node.js and Playwright (npm install playwright; npx playwright install chromium).
// It runs the whole flow twice: a desktop browser, and an iPad-sized touch screen.
// NOTE: the "iPad" run is Chromium pretending to be an iPad (size + touch). It is NOT
// Safari. Real iPad Safari must still be checked by hand (see docs/TESTING.md).

import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = process.env.DNT_TEST_OUT || path.join(ROOT, "tests", "browser", "output");
mkdirSync(OUT, { recursive: true });

const PORT = 8790 + Math.floor(Math.random() * 100);
let BASE = process.env.DNT_TEST_URL || `http://127.0.0.1:${PORT}`;
let server = null;

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
}

async function startServer() {
  if (process.env.DNT_TEST_URL) return;
  const py = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
  server = spawn(py, ["app.py"], {
    cwd: path.join(ROOT, "backend"),
    env: { ...process.env, DNT_DEV_MODE: "1", DNT_PORT: String(PORT), DNT_HOST: "127.0.0.1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  server.stderr.on("data", () => {});
  server.stdout.on("data", () => {});
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`${BASE}/health`); if (r.ok) return; } catch { /* not yet */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("demo server did not start");
}

function stlBounds(buf) {
  const dv = new DataView(buf);
  const n = dv.getUint32(80, true);
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < n; i++) {
    const off = 84 + i * 50 + 12;
    for (let v = 0; v < 3; v++) for (let a = 0; a < 3; a++) {
      const x = dv.getFloat32(off + v * 12 + a * 4, true);
      if (x < lo[a]) lo[a] = x; if (x > hi[a]) hi[a] = x;
    }
  }
  return { triangles: n, size: hi.map((h, i) => Math.round((h - lo[i]) * 10) / 10) };
}

async function coveredPixels(page) {
  // Share of viewer pixels that are clearly the orange model (solid surface, not dots).
  return page.evaluate(() => {
    const src = document.querySelector("#viewerStage canvas");
    const c = document.createElement("canvas");
    c.width = 200; c.height = Math.round(200 * src.height / src.width);
    const ctx = c.getContext("2d");
    ctx.drawImage(src, 0, 0, c.width, c.height);
    const d = ctx.getImageData(0, 0, c.width, c.height).data;
    let n = 0;
    for (let i = 0; i < d.length; i += 4) {
      const [r, g, b] = [d[i], d[i + 1], d[i + 2]];
      if (r > g + 25 && g > b + 10) n++;
    }
    return n / (c.width * c.height);
  });
}

async function runProfile(browser, label, contextOptions) {
  const ctx = await browser.newContext({ ...contextOptions, acceptDownloads: true });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

  await page.goto(BASE + "/");
  check(`[${label}] / redirects to the student app`, page.url().endsWith("/app/"), page.url());
  await page.waitForSelector("#modeBadge.badge-demo", { timeout: 10000 });
  check(`[${label}] demo mode is clearly shown`, await page.isVisible("#demoBanner"));

  // Upload the owl sketch through the normal file picker.
  await page.setInputFiles("#fileInput", path.join(ROOT, "sample-data/sketches/owl.png"));
  await page.waitForSelector("#editArea:not([hidden])");
  const canvasBox = await page.locator("#editorCanvas").boundingBox();
  check(`[${label}] sketch preview appears`, canvasBox && canvasBox.width > 100, JSON.stringify(canvasBox));

  // Crop by dragging the top-left handle inwards, then rotate twice (back to upright).
  const b = canvasBox;
  await page.mouse.move(b.x + 2, b.y + 2);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width * 0.1, b.y + b.height * 0.05, { steps: 5 });
  await page.mouse.up();
  const crop = await page.evaluate(() => window.__dntEditorCrop?.() ?? null);
  void crop;
  await page.click("#rotRight");
  await page.click("#rotLeft");
  await page.fill("#modelName", "Test Owl");
  await page.click('#baseChoiceStart [data-base="plinth"]');
  await page.click("#generateBtn");
  await page.waitForSelector("#stepResult:not([hidden])", { timeout: 90000 });
  check(`[${label}] only the result step is on screen`, !(await page.isVisible("#stepSketch")) && !(await page.isVisible("#stepProgress")));
  check(`[${label}] result shows the SAMPLE warning`, (await page.textContent("#resultBanner")).includes("not"));

  await page.waitForFunction(() => window.__dnt.viewer && window.__dnt.viewer.stats.loaded, null, { timeout: 30000 });
  await page.waitForTimeout(800);
  const stats = await page.evaluate(() => window.__dnt.viewer.stats);
  check(`[${label}] viewer loaded a triangle mesh`, stats.triangles > 1000, `${stats.triangles} triangles`);
  check(`[${label}] model fits 40 × 40 × 60 mm`, stats.sizeMm[0] <= 40.01 && stats.sizeMm[1] <= 40.01 && stats.sizeMm[2] <= 60.01, stats.sizeMm.join(" × "));
  const cover = await coveredPixels(page);
  check(`[${label}] model is drawn as a solid surface`, cover > 0.03, `${(cover * 100).toFixed(1)}% of viewer is model`);
  await page.locator(".viewer-card").screenshot({ path: path.join(OUT, `${label}-viewer.png`) });

  for (const v of ["front", "back", "left", "right", "top", "bottom"]) {
    await page.click(`[data-view="${v}"]`);
    const ok = await page.evaluate((name) => window.__dnt.viewer.stats.view === name, v);
    if (!ok) check(`[${label}] view button ${v}`, false);
  }
  await page.waitForTimeout(400);
  await page.locator(".viewer-card").screenshot({ path: path.join(OUT, `${label}-bottom-view.png`) });
  check(`[${label}] all six view buttons work`, true);
  await page.click('[data-action="wireframe"]');
  check(`[${label}] wireframe toggles`, await page.evaluate(() => window.__dnt.viewer.mesh.material.wireframe === true));
  await page.click('[data-action="wireframe"]');
  await page.click('[data-action="reset"]');

  const items = await page.locator("#reportList li").count();
  const overall = await page.getAttribute("#reportOverall", "class");
  check(`[${label}] printability report shows 5 checks`, items === 5, `${items} items, ${overall}`);
  check(`[${label}] owl sample passes`, overall.includes("pass"));

  // Download STL and compare its size with what the viewer shows.
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#dlStl")]);
  check(`[${label}] STL download has a proper file name`, dl.suggestedFilename() === "Test-Owl.stl", dl.suggestedFilename());
  const stlPath = path.join(OUT, `${label}.stl`);
  await dl.saveAs(stlPath);
  const fs = await import("node:fs");
  const buf = fs.readFileSync(stlPath);
  const bounds = stlBounds(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  check(`[${label}] downloaded STL matches the viewer`, bounds.size.every((v, i) => Math.abs(v - stats.sizeMm[i]) < 0.15), `STL ${bounds.size.join("×")} vs viewer ${stats.sizeMm.join("×")}`);
  const [dl3] = await Promise.all([page.waitForEvent("download"), page.click("#dl3mf")]);
  const p3 = path.join(OUT, `${label}.3mf`);
  await dl3.saveAs(p3);
  check(`[${label}] 3MF download is a 3MF package`, fs.readFileSync(p3).subarray(0, 2).toString() === "PK", dl3.suggestedFilename());

  // Adjust: half size, then rotate, then undo both.
  await page.evaluate(() => { const s = document.getElementById("sizeSlider"); s.value = 50; s.dispatchEvent(new Event("input")); s.dispatchEvent(new Event("change")); });
  check(`[${label}] downloads are locked while the print file updates`, (await page.getAttribute("#dlStl", "aria-disabled")) === "true");
  await page.waitForSelector("#viewerBusy[hidden]", { state: "attached", timeout: 60000 });
  const half = await page.evaluate(() => window.__dnt.viewer.stats.sizeMm);
  check(`[${label}] size 50% halves the model`, Math.abs(half[2] - stats.sizeMm[2] / 2) < 1.5, half.join(" × "));
  await page.click('[data-rot="x,90"]');
  await page.waitForSelector("#viewerBusy[hidden]", { state: "attached", timeout: 60000 });
  const tipped = await page.evaluate(() => window.__dnt.viewer.stats.sizeMm);
  // Lying down: the long side is now depth (Y), and it still fits the 50% box (20 × 20 × 30 mm).
  check(`[${label}] tipping forward 90° lays the model down`, tipped[1] > tipped[2] * 1.3 && tipped[1] <= 20.05, tipped.join(" × "));
  await page.click("#undoBtn");
  await page.click("#undoBtn");
  await page.waitForFunction(() => !window.__dnt.state.busy, null, { timeout: 60000 });
  await page.waitForTimeout(300);
  const back = await page.evaluate(() => window.__dnt.viewer.stats.sizeMm);
  check(`[${label}] undo returns to the original size`, back.every((v, i) => Math.abs(v - stats.sizeMm[i]) < 0.3), back.join(" × "));
  check(`[${label}] redo is available after undo`, !(await page.isDisabled("#redoBtn")));

  // Robot sample shows warnings.
  await page.click("#startAgain");
  await page.click('[data-sample="robot"]');
  await page.click("#generateBtn");
  await page.waitForSelector("#stepResult:not([hidden])", { timeout: 90000 });
  await page.waitForFunction(() => document.querySelectorAll("#reportList li").length === 5);
  const warnText = await page.textContent("#reportList");
  check(`[${label}] robot sample warns about loose piece and thin part`, warnText.includes("separate pieces") && warnText.includes("thinner"));
  await page.screenshot({ path: path.join(OUT, `${label}-robot-full.png`), fullPage: true });

  check(`[${label}] no JavaScript errors`, errors.length === 0, errors.slice(0, 3).join(" | "));
  await ctx.close();
}

async function accessCodeFlow(browser) {
  // A second demo server that requires an access code, like the iPad (LAN) setup.
  if (process.env.DNT_TEST_URL) return;
  const port = PORT + 1;
  const py = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
  const srv = spawn(py, ["app.py"], {
    cwd: path.join(ROOT, "backend"),
    env: { ...process.env, DNT_DEV_MODE: "1", DNT_PORT: String(port), DNT_HOST: "127.0.0.1", DNT_ACCESS_CODE: "TEST42" },
    stdio: "ignore",
  });
  const base = `http://127.0.0.1:${port}`;
  try {
    for (let i = 0; i < 60; i++) {
      try { if ((await fetch(`${base}/health`)).ok) break; } catch { /* wait */ }
      await new Promise((r) => setTimeout(r, 500));
    }
    const ctx = await browser.newContext({ ...devices["iPad Pro 11"] });
    const page = await ctx.newPage();
    await page.goto(base + "/");
    await page.waitForSelector("#codeDialog[open]", { timeout: 10000 });
    check("[access code] the code box appears", true);
    await page.fill("#codeInput", "WRONG");
    await page.click("#codeSubmit");
    await page.waitForSelector("#codeError:not([hidden])");
    check("[access code] a wrong code is refused", true);
    await page.fill("#codeInput", "test42");
    await page.click("#codeSubmit");
    await page.waitForSelector("#codeDialog:not([open])", { state: "attached" });
    await page.click('[data-sample="owl"]');
    await page.click("#generateBtn");
    await page.waitForSelector("#stepResult:not([hidden])", { timeout: 90000 });
    check("[access code] after the right code, the full flow works", true);
    await ctx.close();
  } catch (e) {
    check("[access code] flow", false, String(e).slice(0, 200));
  } finally {
    srv.kill();
  }
}

async function main() {
  await startServer();
  const browser = await chromium.launch();
  try {
    await runProfile(browser, "desktop", { viewport: { width: 1366, height: 900 } });
    await runProfile(browser, "ipad-emulated", { ...devices["iPad Pro 11"] });
    await runProfile(browser, "ipad-portrait-dark", { ...devices["iPad Pro 11"], colorScheme: "dark" });
    await accessCodeFlow(browser);
  } finally {
    await browser.close();
    if (server) server.kill();
  }
  const failed = results.filter((r) => !r.ok);
  writeFileSync(path.join(OUT, "results.json"), JSON.stringify(results, null, 2));
  console.log(`\n${results.length - failed.length}/${results.length} browser checks passed. Screenshots in ${OUT}`);
  process.exit(failed.length ? 1 : 0);
}

main().catch((e) => { console.error(e); if (server) server.kill(); process.exit(2); });
