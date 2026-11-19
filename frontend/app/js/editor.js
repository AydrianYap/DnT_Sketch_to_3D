// Sketch editor: crop, rotate, brightness and contrast before upload.
//
// Works with finger, Apple Pencil and mouse (Pointer Events). The output is always a
// JPEG made on a canvas, so iPad photos in HEIC format are converted automatically.

const MAX_OUTPUT_SIDE = 2048;
const HANDLE_HIT = 34; // px: generous for fingers

export class SketchEditor {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.image = null;      // HTMLImageElement
    this.name = "sketch";
    this.rotation = 0;      // 0, 90, 180, 270
    this.brightness = 1;
    this.contrast = 1;
    this.crop = { x: 0, y: 0, w: 1, h: 1 }; // fraction of the rotated image
    this.drag = null;
    this.onChange = () => {};

    canvas.addEventListener("pointerdown", (e) => this._down(e));
    canvas.addEventListener("pointermove", (e) => this._move(e));
    canvas.addEventListener("pointerup", (e) => this._up(e));
    canvas.addEventListener("pointercancel", (e) => this._up(e));
    new ResizeObserver(() => this.draw()).observe(canvas.parentElement);
  }

  get hasImage() { return !!this.image; }

  async load(file) {
    const objectUrl = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.decoding = "async";
      img.src = objectUrl;
      await img.decode();
      this.image = img;
    } catch (e) {
      URL.revokeObjectURL(objectUrl);
      throw new Error("This file could not be opened as a picture. Try a JPG or PNG photo.");
    }
    this._objectUrl && URL.revokeObjectURL(this._objectUrl);
    this._objectUrl = objectUrl;
    this.name = (file.name || "sketch").replace(/\.[^.]+$/, "").replace(/[^\w-]+/g, "-").slice(0, 40) || "sketch";
    this.reset();
  }

  clear() {
    this._objectUrl && URL.revokeObjectURL(this._objectUrl);
    this._objectUrl = null;
    this.image = null;
    this.draw();
    this.onChange();
  }

  reset() {
    this.rotation = 0;
    this.brightness = 1;
    this.contrast = 1;
    this.crop = { x: 0, y: 0, w: 1, h: 1 };
    this.draw();
    this.onChange();
  }

  rotate(deg) {
    this.rotation = (this.rotation + deg + 360) % 360;
    // keep the crop on the same part of the picture
    const c = this.crop;
    this.crop = deg > 0
      ? { x: 1 - c.y - c.h, y: c.x, w: c.h, h: c.w }
      : { x: c.y, y: 1 - c.x - c.w, w: c.h, h: c.w };
    this.draw();
    this.onChange();
  }

  setBrightness(v) { this.brightness = v; this.draw(); this.onChange(); }
  setContrast(v) { this.contrast = v; this.draw(); this.onChange(); }

  _rotatedSize() {
    const w = this.image.naturalWidth, h = this.image.naturalHeight;
    return this.rotation % 180 === 0 ? [w, h] : [h, w];
  }

  _drawRotated(ctx, scale) {
    const [rw, rh] = this._rotatedSize();
    ctx.save();
    ctx.translate((rw * scale) / 2, (rh * scale) / 2);
    ctx.rotate((this.rotation * Math.PI) / 180);
    ctx.drawImage(this.image, (-this.image.naturalWidth * scale) / 2, (-this.image.naturalHeight * scale) / 2,
      this.image.naturalWidth * scale, this.image.naturalHeight * scale);
    ctx.restore();
  }

  _layout() {
    const box = this.canvas.parentElement.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const [rw, rh] = this._rotatedSize();
    const scale = Math.min(box.width / rw, box.height / rh);
    const cw = Math.max(1, Math.round(rw * scale));
    const ch = Math.max(1, Math.round(rh * scale));
    return { dpr, scale, cw, ch };
  }

  draw() {
    const { canvas, ctx } = this;
    if (!this.image) {
      canvas.width = canvas.height = 1;
      return;
    }
    const { dpr, scale, cw, ch } = this._layout();
    canvas.width = cw * dpr;
    canvas.height = ch * dpr;
    canvas.style.width = cw + "px";
    canvas.style.height = ch + "px";
    // CSS filters preview the same formula used for the final picture (see export()).
    canvas.style.filter = `brightness(${this.brightness}) contrast(${this.contrast})`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    this._drawRotated(ctx, scale);

    const c = this.crop;
    const x = c.x * cw, y = c.y * ch, w = c.w * cw, h = c.h * ch;
    ctx.fillStyle = "rgba(15, 23, 42, 0.5)";
    ctx.beginPath();
    ctx.rect(0, 0, cw, ch);
    ctx.rect(x, y, w, h);
    ctx.fill("evenodd");
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    ctx.strokeStyle = "rgba(255,255,255,0.45)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 3; i++) { // rule-of-thirds guides
      ctx.beginPath(); ctx.moveTo(x + (w * i) / 3, y); ctx.lineTo(x + (w * i) / 3, y + h); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x, y + (h * i) / 3); ctx.lineTo(x + w, y + (h * i) / 3); ctx.stroke();
    }
    ctx.fillStyle = "#ffffff";
    for (const [hx, hy] of [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]) {
      ctx.beginPath(); ctx.arc(hx, hy, 9, 0, Math.PI * 2); ctx.fill();
    }
    this._view = { cw, ch };
  }

  _pos(e) {
    const r = this.canvas.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  _down(e) {
    if (!this.image || !this._view) return;
    const [px, py] = this._pos(e);
    const { cw, ch } = this._view;
    const c = this.crop;
    const x0 = c.x * cw, y0 = c.y * ch, x1 = (c.x + c.w) * cw, y1 = (c.y + c.h) * ch;
    const near = (a, b) => Math.abs(a - b) < HANDLE_HIT;
    let mode = null;
    if (near(px, x0) && near(py, y0)) mode = "nw";
    else if (near(px, x1) && near(py, y0)) mode = "ne";
    else if (near(px, x0) && near(py, y1)) mode = "sw";
    else if (near(px, x1) && near(py, y1)) mode = "se";
    else if (px > x0 && px < x1 && py > y0 && py < y1) mode = "move";
    if (!mode) return;
    e.preventDefault();
    this.canvas.setPointerCapture(e.pointerId);
    this.drag = { mode, start: [px, py], crop: { ...c } };
  }

  _move(e) {
    if (!this.drag) return;
    e.preventDefault();
    const [px, py] = this._pos(e);
    const { cw, ch } = this._view;
    const dx = (px - this.drag.start[0]) / cw;
    const dy = (py - this.drag.start[1]) / ch;
    const s = this.drag.crop;
    const min = 0.08;
    let { x, y, w, h } = s;
    const m = this.drag.mode;
    if (m === "move") {
      x = Math.min(Math.max(s.x + dx, 0), 1 - s.w);
      y = Math.min(Math.max(s.y + dy, 0), 1 - s.h);
    } else {
      if (m.includes("w")) { x = Math.min(Math.max(s.x + dx, 0), s.x + s.w - min); w = s.x + s.w - x; }
      if (m.includes("e")) { w = Math.min(Math.max(s.w + dx, min), 1 - s.x); }
      if (m.includes("n")) { y = Math.min(Math.max(s.y + dy, 0), s.y + s.h - min); h = s.y + s.h - y; }
      if (m.includes("s")) { h = Math.min(Math.max(s.h + dy, min), 1 - s.y); }
    }
    this.crop = { x, y, w, h };
    this.draw();
  }

  _up(e) {
    if (!this.drag) return;
    this.drag = null;
    try { this.canvas.releasePointerCapture(e.pointerId); } catch { /* ignore */ }
    this.onChange();
  }

  /** The edited picture as a JPEG Blob, plus a file name for upload. */
  async export() {
    const [rw, rh] = this._rotatedSize();
    const c = this.crop;
    const cropW = c.w * rw, cropH = c.h * rh;
    const outScale = Math.min(1, MAX_OUTPUT_SIDE / Math.max(cropW, cropH));
    const full = document.createElement("canvas");
    full.width = Math.round(rw * outScale);
    full.height = Math.round(rh * outScale);
    const fctx = full.getContext("2d");
    fctx.fillStyle = "#ffffff";
    fctx.fillRect(0, 0, full.width, full.height);
    this._drawRotated(fctx, outScale);

    const out = document.createElement("canvas");
    out.width = Math.max(1, Math.round(cropW * outScale));
    out.height = Math.max(1, Math.round(cropH * outScale));
    const octx = out.getContext("2d");
    octx.drawImage(full, Math.round(c.x * full.width), Math.round(c.y * full.height), out.width, out.height,
      0, 0, out.width, out.height);

    if (this.brightness !== 1 || this.contrast !== 1) {
      // Same maths as CSS brightness()/contrast(), done by hand because older iPad
      // Safari versions ignore canvas filters.
      const img = octx.getImageData(0, 0, out.width, out.height);
      const d = img.data, b = this.brightness, k = this.contrast;
      for (let i = 0; i < d.length; i += 4) {
        for (let j = 0; j < 3; j++) {
          const v = d[i + j] * b;
          d[i + j] = (v - 127.5) * k + 127.5;
        }
      }
      octx.putImageData(img, 0, 0);
    }
    const blob = await new Promise((resolve) => out.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) throw new Error("Could not prepare the picture.");
    return { blob, filename: `${this.name}.jpg`, width: out.width, height: out.height };
  }
}
