// Solid-surface 3D viewer for print-ready STL files (Three.js).
//
// Units are millimetres and Z points up, matching the exported STL/3MF.
// Touch: one finger rotates, pinch zooms, two fingers pan (OrbitControls defaults).

import * as THREE from "../vendor/three.module.min.js";
import { OrbitControls } from "../vendor/OrbitControls.js";
import { STLLoader } from "../vendor/STLLoader.js";
import { toCreasedNormals } from "../vendor/BufferGeometryUtils.js";

// Which side is the "front" of the figurine. The sample models face -Y.
// (To be confirmed against real TripoSR output during the Lenovo test.)
const VIEW_DIRECTIONS = {
  front: [0, -1, 0.0001],
  back: [0, 1, 0.0001],
  left: [-1, 0, 0.0001],
  right: [1, 0, 0.0001],
  top: [0, -0.0001, 1],
  bottom: [0, 0.0001, -1],
  angle: [0.9, -1.4, 0.8],
};

export class ModelViewer {
  constructor(container, { printBox = [40, 40, 60] } = {}) {
    this.container = container;
    this.printBox = printBox;
    this.mesh = null;
    this.wireframe = false;
    this.stats = { loaded: false, triangles: 0, sizeMm: null, view: "angle" };

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-label", "3D model viewer. Drag to rotate, pinch to zoom, two fingers to pan.");
    renderer.domElement.setAttribute("role", "img");
    this.renderer = renderer;

    const scene = new THREE.Scene();
    this.scene = scene;
    this._applyTheme();

    const camera = new THREE.PerspectiveCamera(35, 1, 0.5, 2000);
    camera.up.set(0, 0, 1);
    camera.position.set(90, -140, 80);
    this.camera = camera;

    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(60, -90, 120);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xdfe8ff, 0.9);
    fill.position.set(-90, 40, 60);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffffff, 0.6);
    rim.position.set(0, 120, 40);
    scene.add(rim);

    this._buildGround();

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.screenSpacePanning = true;
    controls.minDistance = 15;
    controls.maxDistance = 600;
    controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
    controls.target.set(0, 0, 25);
    this.controls = controls;

    this._resize = this._resize.bind(this);
    new ResizeObserver(this._resize).observe(container);
    window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", () => this._applyTheme());
    this._resize();
    this._animate = this._animate.bind(this);
    renderer.setAnimationLoop(this._animate);
  }

  _isDark() {
    const forced = document.documentElement.dataset.theme;
    if (forced) return forced === "dark";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  }

  _applyTheme() {
    const dark = this._isDark();
    this.scene.background = new THREE.Color(dark ? 0x1b1f27 : 0xf1f4f8);
    if (this.grid) this.scene.remove(this.grid);
    const [bx, by] = this.printBox;
    const size = 100;
    this.grid = new THREE.GridHelper(size, size / 10, dark ? 0x4b5563 : 0xb8c0cc, dark ? 0x2f3642 : 0xdde2e9);
    this.grid.rotation.x = Math.PI / 2; // GridHelper lies in XZ; turn it to XY (Z up)
    this.grid.position.z = -0.01;
    this.scene.add(this.grid);
    if (this.floor) this.floor.material.color.set(dark ? 0x222833 : 0xe6eaf0);
    void bx; void by;
  }

  _buildGround() {
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(100, 100),
      new THREE.MeshStandardMaterial({ color: 0xe6eaf0, roughness: 1, metalness: 0 }),
    );
    floor.position.z = -0.05;
    this.floor = floor;
    this.scene.add(floor);
    this._applyTheme();

    // The maximum print volume, drawn as a dashed box so students see the limit.
    const [bx, by, bz] = this.printBox;
    const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(bx, by, bz));
    const box = new THREE.LineSegments(edges, new THREE.LineDashedMaterial({
      color: 0x2b8a8a, dashSize: 2, gapSize: 1.5, transparent: true, opacity: 0.7,
    }));
    box.computeLineDistances();
    box.position.z = bz / 2;
    this.printBoxHelper = box;
    this.scene.add(box);

    // Small axis hint at the front-left corner: red = X (width), green = Y (depth), blue = Z (height).
    const axes = new THREE.AxesHelper(8);
    axes.position.set(-bx / 2 - 6, -by / 2 - 6, 0);
    this.scene.add(axes);
  }

  _resize() {
    const w = Math.max(this.container.clientWidth, 1);
    const h = Math.max(this.container.clientHeight, 1);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  _animate() {
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  /** Show an STL file (ArrayBuffer). Keeps the camera unless keepCamera is false. */
  showStl(arrayBuffer, { keepCamera = false } = {}) {
    const raw = new STLLoader().parse(arrayBuffer);
    // STL stores flat faces; crease-aware normals give smooth curves but keep sharp edges (e.g. a plinth rim).
    const geometry = toCreasedNormals(raw, THREE.MathUtils.degToRad(35));
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();

    const material = new THREE.MeshStandardMaterial({
      color: 0xe0915c, roughness: 0.55, metalness: 0.05, wireframe: this.wireframe,
      side: THREE.DoubleSide, // makes holes visible as dark insides rather than invisible
    });
    const mesh = new THREE.Mesh(geometry, material);

    if (this.mesh) {
      this.scene.remove(this.mesh);
      this.mesh.geometry.dispose();
      this.mesh.material.dispose();
    }
    this.mesh = mesh;
    this.previewTransform = null;
    this.scene.add(mesh);

    const size = new THREE.Vector3();
    geometry.boundingBox.getSize(size);
    this.stats = {
      loaded: true,
      triangles: geometry.attributes.position.count / 3,
      sizeMm: [size.x, size.y, size.z].map((v) => Math.round(v * 10) / 10),
      view: this.stats.view,
    };
    if (!keepCamera) this.setView("angle");
    return this.stats;
  }

  clear() {
    if (this.mesh) {
      this.scene.remove(this.mesh);
      this.mesh.geometry.dispose();
      this.mesh.material.dispose();
      this.mesh = null;
    }
    this.stats = { loaded: false, triangles: 0, sizeMm: null, view: "angle" };
  }

  setWireframe(on) {
    this.wireframe = !!on;
    if (this.mesh) this.mesh.material.wireframe = this.wireframe;
  }

  _targetSphere() {
    if (this.mesh) {
      const box = new THREE.Box3().setFromObject(this.mesh);
      const sphere = new THREE.Sphere();
      box.getBoundingSphere(sphere);
      return sphere;
    }
    const [bx, by, bz] = this.printBox;
    return new THREE.Sphere(new THREE.Vector3(0, 0, bz / 2), Math.hypot(bx, by, bz) / 2);
  }

  /** front | back | left | right | top | bottom | angle */
  setView(name) {
    const dir = new THREE.Vector3(...(VIEW_DIRECTIONS[name] || VIEW_DIRECTIONS.angle)).normalize();
    const sphere = this._targetSphere();
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const fitFov = this.camera.aspect < 1 ? 2 * Math.atan(Math.tan(fov / 2) * this.camera.aspect) : fov;
    const dist = (sphere.radius / Math.sin(fitFov / 2)) * 1.15;
    this.controls.target.copy(sphere.center);
    this.camera.position.copy(sphere.center).addScaledVector(dir, dist);
    // Looking straight down/up needs a different "up" so the view isn't spun randomly.
    this.camera.up.set(0, 0, 1);
    if (name === "top") this.camera.up.set(0, 1, 0);
    if (name === "bottom") this.camera.up.set(0, -1, 0);
    this.camera.lookAt(sphere.center);
    this.controls.update();
    if (name === "top" || name === "bottom") this.camera.up.set(0, 0, 1);
    this.stats.view = name;
  }

  fit() { this.setView(this.stats.view === "top" || this.stats.view === "bottom" ? "angle" : this.stats.view); }

  reset() { this.setView("angle"); }

  /**
   * Instant, approximate preview of a rotation/size change while the server rebuilds
   * the real print file. deltaRot in degrees (X, Y, Z); sizeRatio relative to current file.
   */
  previewAdjust(deltaRot, sizeRatio) {
    if (!this.mesh) return;
    const m = this.mesh;
    m.rotation.set(0, 0, 0);
    m.scale.set(1, 1, 1);
    m.position.set(0, 0, 0);
    m.geometry.computeBoundingBox();
    const centre = new THREE.Vector3();
    m.geometry.boundingBox.getCenter(centre);
    const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(
      THREE.MathUtils.degToRad(deltaRot[0]), THREE.MathUtils.degToRad(deltaRot[1]),
      THREE.MathUtils.degToRad(deltaRot[2]), "ZYX"));
    m.quaternion.copy(q);
    m.scale.setScalar(sizeRatio);
    // rotate/scale about the model's centre, then stand it back on the floor
    const offset = centre.clone().applyQuaternion(q).multiplyScalar(sizeRatio);
    m.position.copy(centre).sub(offset);
    m.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(m);
    m.position.z -= box.min.z;
    m.position.x -= (box.min.x + box.max.x) / 2;
    m.position.y -= (box.min.y + box.max.y) / 2;
  }

  snapshot() {
    return this.renderer.domElement.toDataURL("image/png");
  }
}
