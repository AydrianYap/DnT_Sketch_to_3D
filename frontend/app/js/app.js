// D&T Sketch-to-3D: student interface logic.

import * as api from "./api.js";
import { SketchEditor } from "./editor.js";
import { ModelViewer } from "./viewer.js";

const $ = (id) => document.getElementById(id);

const state = {
  health: null,
  job: null,           // latest job status from the server
  pollTimer: null,
  base: "none",
  // Adjustment history: each entry is { rotate: [x, y, z], size, base }.
  history: [],
  historyIndex: -1,
  applied: null,       // the adjustment the current print file was built with
  applySeq: 0,
  applyTimer: null,
  busy: false,
  sourceUrl: null,
};

const editor = new SketchEditor($("editorCanvas"));
let viewer = null;

// Exposed for automated browser tests and for curious teachers in the console.
window.__dnt = { state, get viewer() { return viewer; } };

// ------------------------------------------------------------------ helpers

function show(el, on = true) { el.hidden = !on; }

function setRadio(groupEl, value) {
  groupEl.querySelectorAll("[role=radio]").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.base === value)));
}

function friendly(err) {
  if (err instanceof api.AccessCodeNeeded) return "This device needs the access code first.";
  return (err && err.message) || String(err);
}

function figurineName() {
  return ($("modelName").value || editor.name || "figurine").trim();
}

// ------------------------------------------------------------------ connection & mode

async function refreshHealth() {
  try {
    const h = await api.health();
    state.health = h;
    $("connDot").className = "dot ok";
    $("connDot").title = "Connected to the 3D engine";
    const badge = $("modeBadge");
    if (h.dev_mode) {
      badge.className = "badge badge-demo";
      badge.textContent = "Demo mode · samples";
      show($("demoBanner"), true);
    } else if (h.triposr) {
      badge.className = "badge badge-ai";
      badge.textContent = `AI mode · TripoSR on ${String(h.runtime_device || "").toUpperCase()}`;
      show($("demoBanner"), false);
    } else {
      badge.className = "badge badge-bad";
      badge.textContent = "AI engine not ready";
      show($("demoBanner"), false);
    }
    return h;
  } catch (e) {
    $("connDot").className = "dot bad";
    $("connDot").title = "Not connected";
    $("modeBadge").className = "badge badge-bad";
    $("modeBadge").textContent = "Not connected";
    return null;
  }
}

async function ensureAccess() {
  const h = state.health || (await refreshHealth());
  if (!h || !h.access_code_required) return;
  try {
    await api.status("access-check"); // 404 = we are allowed in
  } catch (e) {
    if (e instanceof api.AccessCodeNeeded) await askForCode();
  }
}

function askForCode() {
  return new Promise((resolve) => {
    const dlg = $("codeDialog");
    const input = $("codeInput");
    const err = $("codeError");
    show(err, false);
    $("codeForm").onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        await api.login(input.value.trim());
        dlg.close();
        resolve();
      } catch (e) {
        err.textContent = friendly(e);
        show(err, true);
      }
    };
    dlg.showModal();
    input.focus();
  });
}

// ------------------------------------------------------------------ step 1: sketch

async function useFile(file) {
  if (!file) return;
  const okType = !file.type || /^image\//.test(file.type);
  if (!okType) {
    alert("Please choose a picture (JPG, PNG, WEBP or an iPad photo).");
    return;
  }
  try {
    await editor.load(file);
  } catch (e) {
    alert(friendly(e));
    return;
  }
  if (!$("modelName").value) $("modelName").value = editor.name === "sketch" ? "" : editor.name;
  show($("pickArea"), false);
  show($("editArea"), true);
  $("brightness").value = 1;
  $("contrast").value = 1;
  requestAnimationFrame(() => editor.draw());
}

async function useSample(name) {
  const res = await fetch(`samples/${name}.png`);
  const blob = await res.blob();
  await useFile(new File([blob], `${name}.png`, { type: "image/png" }));
}

function clearSketch() {
  editor.clear();
  $("fileInput").value = "";
  $("cameraInput").value = "";
  show($("editArea"), false);
  show($("pickArea"), true);
}

// ------------------------------------------------------------------ step 2: generate

async function generate() {
  if (!editor.hasImage) return;
  await ensureAccess();
  show($("errorCard"), false);
  const btn = $("generateBtn");
  btn.disabled = true;
  try {
    const { blob, filename } = await editor.export();
    if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
    state.sourceUrl = URL.createObjectURL(blob);
    setProgress(2, "Sending your picture…");
    show($("stepSketch"), false);
    show($("stepResult"), false);
    show($("stepProgress"), true);
    $("progressHint").hidden = !(state.health && state.health.runtime_device === "cpu" && !state.health.dev_mode);
    const job = await api.convert(blob, filename, state.base);
    state.job = job;
    poll();
  } catch (e) {
    if (e instanceof api.AccessCodeNeeded) { await askForCode(); btn.disabled = false; show($("stepProgress"), false); show($("stepSketch"), true); return; }
    showError(friendly(e));
  } finally {
    btn.disabled = false;
  }
}

function setProgress(pct, msg) {
  $("progressFill").style.width = `${Math.max(2, Math.min(100, pct))}%`;
  $("progressBar").setAttribute("aria-valuenow", String(pct));
  $("progressMsg").textContent = msg;
}

function poll() {
  clearTimeout(state.pollTimer);
  state.pollTimer = setTimeout(async () => {
    try {
      const job = await api.status(state.job.job_id);
      state.job = job;
      setProgress(job.progress || 0, job.message || job.status);
      if (job.status === "done") return showResult(job);
      if (job.status === "error") return showError(job.message || "The 3D engine reported an error.");
      if (job.status === "cancelled") { show($("stepProgress"), false); show($("stepSketch"), true); return; }
      poll();
    } catch (e) {
      if (e instanceof api.AccessCodeNeeded) { await askForCode(); return poll(); }
      setProgress(state.job.progress || 0, "Lost connection, retrying… " + friendly(e));
      poll();
    }
  }, 1500);
}

function showError(message) {
  clearTimeout(state.pollTimer);
  show($("stepProgress"), false);
  show($("stepResult"), false);
  show($("stepSketch"), true);
  $("errorMsg").textContent = message;
  show($("errorCard"), true);
  $("errorCard").scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------------ step 3: result

async function showResult(job) {
  show($("stepProgress"), false);
  show($("stepSketch"), false);
  show($("stepResult"), true);

  const banner = $("resultBanner");
  if (job.is_sample) {
    banner.className = "banner banner-demo";
    banner.innerHTML = "<strong>Sample model (demo mode).</strong> This was <em>not</em> made from your sketch. " +
      "It is a ready-made sample so you can practise. In AI mode the model is built from your picture.";
  } else {
    banner.className = "banner banner-ai";
    banner.innerHTML = `<strong>Made by AI from your picture</strong> (${job.model_used || "TripoSR"}` +
      `${job.time_taken ? `, ${job.time_taken} s` : ""}). Compare it carefully with your sketch.`;
  }

  if (!viewer) viewer = new ModelViewer($("viewerStage"), { printBox: (state.health && state.health.max_box_mm) || [40, 40, 60] });

  // Compare panel: the picture the server received (falls back to the local copy).
  try {
    if (job.source_image_url) {
      const blob = await api.fetchBlob(job.source_image_url);
      $("compareImg").src = URL.createObjectURL(blob);
    } else if (state.sourceUrl) {
      $("compareImg").src = state.sourceUrl;
    }
  } catch { if (state.sourceUrl) $("compareImg").src = state.sourceUrl; }

  const adj = job.adjustments || { rotate_deg: [0, 0, 0], size_percent: 100, base: job.base_mode || "none" };
  const first = { rotate: adj.rotate_deg.map(Number), size: Number(adj.size_percent), base: adj.base || "none" };
  state.history = [first];
  state.historyIndex = 0;
  state.applied = first;
  syncAdjustControls();

  await loadModel(job, false);
  renderReport(job.print_report);
  updateDownloads(job);
}

async function loadModel(job, keepCamera) {
  const rev = job.revision || 0;
  const buf = await api.fetchArrayBuffer(`${job.stl_url}?v=${rev}`);
  const stats = viewer.showStl(buf, { keepCamera });
  const s = stats.sizeMm;
  $("viewerDims").textContent = `${s[0]} × ${s[1]} × ${s[2]} mm  (W × D × H)`;
}

function renderReport(report) {
  const overall = $("reportOverall");
  const list = $("reportList");
  list.innerHTML = "";
  if (!report) {
    overall.className = "report-overall warn";
    overall.textContent = "No print check available.";
    return;
  }
  const headline = {
    pass: "Looks ready to print ✓",
    warn: "Printable, but check the warnings below",
    fail: "Not ready to print yet. Fix the problems below.",
  };
  overall.className = `report-overall ${report.overall}`;
  overall.textContent = headline[report.overall] || report.overall;
  const icon = { pass: "✓", warn: "!", fail: "✕", skipped: "–", info: "i" };
  for (const c of report.checks || []) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="report-icon ${c.status}" aria-hidden="true">${icon[c.status] || "?"}</span>` +
      `<div><strong></strong><span></span></div>`;
    li.querySelector("strong").textContent = c.label;
    li.querySelector("span:not(.report-icon)").textContent = c.message;
    li.setAttribute("aria-label", `${c.status}: ${c.label}. ${c.message}`);
    list.appendChild(li);
  }
  const notes = (report.notes || []).join(" ");
  $("reportMeta").textContent = [
    report.volume_cm3 != null ? `Material: about ${report.volume_cm3} cm³` : "",
    `${(report.faces || 0).toLocaleString()} triangles`,
    notes,
  ].filter(Boolean).join(" · ");
}

function updateDownloads(job, pending = false) {
  const name = encodeURIComponent(figurineName());
  const rev = job.revision || 0;
  const links = [["dlStl", "stl"], ["dl3mf", "3mf"], ["dlReport", "report"]];
  for (const [id, kind] of links) {
    const a = $(id);
    const path = `/download/${job.job_id}/${kind}?name=${name}&v=${rev}`;
    a.href = api.url(path);
    a.dataset.path = path;
    a.setAttribute("aria-disabled", String(pending));
  }
  $("downloadNote").textContent = pending
    ? "Updating the print file with your changes… downloads will be ready in a moment."
    : (job.is_sample ? "These files are the sample model, not a model of your sketch." :
      "The files match the model shown above, sized in millimetres.");
}

// Cross-origin setups (future Cloudflare page) cannot rely on cookies for links,
// so downloads are fetched with the access code and saved from a Blob instead.
async function downloadViaBlob(ev) {
  if (api.isSameOrigin()) return; // normal link works
  ev.preventDefault();
  const a = ev.currentTarget;
  const blob = await api.fetchBlob(a.dataset.path);
  const tmp = document.createElement("a");
  tmp.href = URL.createObjectURL(blob);
  const kind = a.id === "dlStl" ? "stl" : a.id === "dl3mf" ? "3mf" : "json";
  tmp.download = `${figurineName().replace(/[^\w-]+/g, "-")}.${kind}`;
  document.body.appendChild(tmp);
  tmp.click();
  setTimeout(() => { URL.revokeObjectURL(tmp.href); tmp.remove(); }, 2000);
}

// ------------------------------------------------------------------ adjustments

function current() { return state.history[state.historyIndex]; }

function syncAdjustControls() {
  const c = current();
  $("sizeSlider").value = c.size;
  $("sizeValue").textContent = `${c.size}%`;
  setRadio($("baseChoiceAdjust"), c.base);
  $("undoBtn").disabled = state.historyIndex <= 0;
  $("redoBtn").disabled = state.historyIndex >= state.history.length - 1;
}

function pushAdjustment(change) {
  const c = current();
  const next = {
    rotate: change.rotate || [...c.rotate],
    size: change.size ?? c.size,
    base: change.base ?? c.base,
  };
  state.history = state.history.slice(0, state.historyIndex + 1);
  state.history.push(next);
  state.historyIndex = state.history.length - 1;
  afterAdjustmentChange();
}

function afterAdjustmentChange() {
  syncAdjustControls();
  const c = current();
  const a = state.applied;
  // Instant approximate preview; the exact print file follows from the server.
  const delta = [0, 1, 2].map((i) => c.rotate[i] - a.rotate[i]);
  viewer && viewer.previewAdjust(delta, c.size / a.size);
  scheduleApply();
}

function scheduleApply() {
  clearTimeout(state.applyTimer);
  setBusy(true);
  state.applyTimer = setTimeout(applyNow, 450);
}

function setBusy(on) {
  state.busy = on;
  show($("viewerBusy"), on);
  if (state.job) updateDownloads(state.job, on);
  $("adjustStatus").textContent = on
    ? "Preview shown. Updating the print file and checks…"
    : "Print file is up to date. The model always sits in the middle of the print plate.";
}

async function applyNow() {
  const target = current();
  const seq = ++state.applySeq;
  try {
    const job = await api.adjust(state.job.job_id, target);
    if (seq !== state.applySeq) return; // a newer change is on its way
    state.job = job;
    state.applied = target;
    await loadModel(job, true);
    renderReport(job.print_report);
    setBusy(false);
  } catch (e) {
    if (seq !== state.applySeq) return;
    if (e instanceof api.AccessCodeNeeded) { await askForCode(); return applyNow(); }
    setBusy(false);
    $("adjustStatus").textContent = "Could not apply that change: " + friendly(e);
    // go back to what the print file really is
    viewer.previewAdjust([0, 0, 0], 1);
  }
}

function rotateBy(axis, deg) {
  const idx = { x: 0, y: 1, z: 2 }[axis];
  const r = [...current().rotate];
  r[idx] = ((r[idx] + deg + 540) % 360) - 180;
  pushAdjustment({ rotate: r });
}

// ------------------------------------------------------------------ wiring

function wire() {
  $("fileInput").addEventListener("change", (e) => useFile(e.target.files[0]));
  $("cameraInput").addEventListener("change", (e) => useFile(e.target.files[0]));
  document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", () => useSample(b.dataset.sample)));

  const pick = $("pickArea");
  pick.addEventListener("dragover", (e) => { e.preventDefault(); pick.classList.add("dragover"); });
  pick.addEventListener("dragleave", () => pick.classList.remove("dragover"));
  pick.addEventListener("drop", (e) => { e.preventDefault(); pick.classList.remove("dragover"); useFile(e.dataTransfer.files[0]); });

  $("rotLeft").addEventListener("click", () => editor.rotate(-90));
  $("rotRight").addEventListener("click", () => editor.rotate(90));
  $("editReset").addEventListener("click", () => { editor.reset(); $("brightness").value = 1; $("contrast").value = 1; });
  $("brightness").addEventListener("input", (e) => editor.setBrightness(Number(e.target.value)));
  $("contrast").addEventListener("input", (e) => editor.setContrast(Number(e.target.value)));
  $("deleteSketch").addEventListener("click", () => { if (confirm("Delete this picture?")) clearSketch(); });

  $("baseChoiceStart").addEventListener("click", (e) => {
    const b = e.target.closest("[data-base]"); if (!b) return;
    state.base = b.dataset.base; setRadio($("baseChoiceStart"), state.base);
  });
  $("generateBtn").addEventListener("click", generate);
  $("cancelBtn").addEventListener("click", async () => {
    if (state.job) { try { await api.cancel(state.job.job_id); } catch { /* ignore */ } }
    setProgress(state.job ? state.job.progress : 0, "Cancelling…");
  });
  $("errorRetry").addEventListener("click", () => { show($("errorCard"), false); generate(); });
  $("errorBack").addEventListener("click", () => show($("errorCard"), false));

  document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => viewer && viewer.setView(b.dataset.view)));
  document.querySelector("[data-action=fit]").addEventListener("click", () => viewer && viewer.fit());
  document.querySelector("[data-action=reset]").addEventListener("click", () => viewer && viewer.reset());
  const wf = document.querySelector("[data-action=wireframe]");
  wf.addEventListener("click", () => {
    const on = wf.getAttribute("aria-pressed") !== "true";
    wf.setAttribute("aria-pressed", String(on));
    viewer && viewer.setWireframe(on);
  });
  $("matchFront").addEventListener("click", () => viewer && viewer.setView("front"));

  document.querySelectorAll("[data-rot]").forEach((b) => b.addEventListener("click", () => {
    const [axis, deg] = b.dataset.rot.split(",");
    rotateBy(axis, Number(deg));
  }));
  const size = $("sizeSlider");
  size.addEventListener("input", () => { $("sizeValue").textContent = `${size.value}%`; });
  size.addEventListener("change", () => pushAdjustment({ size: Number(size.value) }));
  $("baseChoiceAdjust").addEventListener("click", (e) => {
    const b = e.target.closest("[data-base]"); if (!b || b.dataset.base === current().base) return;
    pushAdjustment({ base: b.dataset.base });
  });
  $("undoBtn").addEventListener("click", () => { if (state.historyIndex > 0) { state.historyIndex--; afterAdjustmentChange(); } });
  $("redoBtn").addEventListener("click", () => { if (state.historyIndex < state.history.length - 1) { state.historyIndex++; afterAdjustmentChange(); } });
  $("adjustReset").addEventListener("click", () => pushAdjustment({ rotate: [0, 0, 0], size: 100, base: current().base }));

  ["dlStl", "dl3mf", "dlReport"].forEach((id) => $(id).addEventListener("click", downloadViaBlob));
  $("modelName").addEventListener("change", () => state.job && state.job.status === "done" && updateDownloads(state.job, state.busy));

  $("startAgain").addEventListener("click", () => {
    show($("stepResult"), false);
    clearSketch();
    $("modelName").value = "";
    show($("stepSketch"), true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

wire();
refreshHealth().then(ensureAccess);
setInterval(refreshHealth, 15000);
