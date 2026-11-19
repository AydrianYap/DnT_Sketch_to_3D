"""
Generate the sample sketches and pre-made meshes used by development mode.

Everything here is drawn/modelled procedurally by this script, so the samples
carry no third-party copyright and share this project's GPL-3.0 licence.

    python scripts/make_samples.py

Writes:
    sample-data/sketches/owl.png          coloured sketch of an owl figurine
    sample-data/sketches/robot.png        coloured sketch of a robot figurine
    sample-data/meshes/owl.stl            clean, printable owl (one piece)
    sample-data/meshes/robot.stl          robot with deliberate problems:
                                          a loose floating part and a thin antenna
The meshes stand in for AI output so the app can be tested without a GPU. They
are NOT AI results.
"""
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from skimage import measure

ROOT = Path(__file__).resolve().parent.parent
SKETCH_DIR = ROOT / "sample-data" / "sketches"
MESH_DIR = ROOT / "sample-data" / "meshes"


# --------------------------------------------------------------------------
# Signed distance helpers (negative = inside)
# --------------------------------------------------------------------------

def ellipsoid(p, c, r):
    q = (p - np.asarray(c)) / np.asarray(r)
    k = np.linalg.norm(q, axis=-1)
    return (k - 1.0) * np.min(r)


def capsule(p, a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0.0, 1.0)
    return np.linalg.norm(pa - h[..., None] * ba, axis=-1) - r


def rounded_box(p, c, half, r):
    q = np.abs(p - np.asarray(c)) - (np.asarray(half) - r)
    return np.linalg.norm(np.maximum(q, 0.0), axis=-1) + np.minimum(q.max(axis=-1), 0.0) - r


def smooth_union(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def sdf_to_mesh(sdf_fn, lo, hi, n=110):
    xs = np.linspace(lo[0], hi[0], n)
    ys = np.linspace(lo[1], hi[1], n)
    zs = np.linspace(lo[2], hi[2], int(n * (hi[2] - lo[2]) / (hi[0] - lo[0])))
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1)
    vol = sdf_fn(grid)
    spacing = (xs[1] - xs[0], ys[1] - ys[0], zs[1] - zs[0])
    verts, faces, _, _ = measure.marching_cubes(vol, level=0.0, spacing=spacing)
    verts += np.asarray(lo)
    mesh = trimesh.Trimesh(verts, faces, process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


# --------------------------------------------------------------------------
# Models (units are arbitrary; the app rescales to 40 x 40 x 60 mm)
# --------------------------------------------------------------------------

def owl_sdf(p):
    d = ellipsoid(p, (0, 0, 1.1), (1.0, 0.85, 1.15))                # body
    d = smooth_union(d, ellipsoid(p, (0, 0, 2.45), (0.85, 0.75, 0.7)), 0.3)  # head
    for s in (-1, 1):
        d = smooth_union(d, capsule(p, (0.45 * s, 0, 2.9), (0.7 * s, 0, 3.35), 0.18), 0.15)  # ears
        d = smooth_union(d, ellipsoid(p, (0.95 * s, 0.05, 1.2), (0.25, 0.55, 0.75)), 0.15)   # wings
        d = smooth_union(d, ellipsoid(p, (0.35 * s, -0.3, 0.05), (0.3, 0.4, 0.15)), 0.15)    # feet
        d = smooth_union(d, ellipsoid(p, (0.32 * s, -0.62, 2.55), (0.22, 0.12, 0.22)), 0.05)  # eyes
    d = smooth_union(d, ellipsoid(p, (0, -0.75, 2.3), (0.1, 0.15, 0.15)), 0.05)           # beak
    return d


def robot_sdf(p):
    d = rounded_box(p, (0, 0, 1.2), (0.8, 0.55, 0.75), 0.12)               # torso
    d = np.minimum(d, rounded_box(p, (0, 0, 2.45), (0.6, 0.5, 0.45), 0.12))  # head
    d = np.minimum(d, capsule(p, (0, 0, 1.9), (0, 0, 2.1), 0.22))           # neck
    for s in (-1, 1):
        d = np.minimum(d, capsule(p, (0.4 * s, 0, 0.45), (0.4 * s, 0, 0.05), 0.22))   # legs
        d = np.minimum(d, capsule(p, (0.95 * s, 0, 1.7), (1.15 * s, -0.2, 0.9), 0.15))  # arms
    # Deliberate problem 1: a thin antenna (too thin to print at figurine scale)
    d = np.minimum(d, capsule(p, (0, 0, 2.85), (0, 0, 3.45), 0.03))
    # Deliberate problem 2: a floating "power orb" not attached to anything
    d = np.minimum(d, ellipsoid(p, (1.45, 0, 2.7), (0.2, 0.2, 0.2)))
    return d


# --------------------------------------------------------------------------
# Sketches
# --------------------------------------------------------------------------

def draw_owl(path):
    img = Image.new("RGB", (768, 1024), (250, 248, 240))
    d = ImageDraw.Draw(img)
    ink = (40, 40, 50)
    d.ellipse((214, 380, 554, 900), fill=(176, 120, 72), outline=ink, width=6)       # body
    d.ellipse((294, 520, 474, 860), fill=(232, 205, 160), outline=ink, width=4)      # belly
    d.ellipse((204, 170, 564, 470), fill=(176, 120, 72), outline=ink, width=6)       # head
    d.polygon([(250, 210), (220, 110), (320, 185)], fill=(150, 98, 58), outline=ink)  # ears
    d.polygon([(518, 210), (548, 110), (448, 185)], fill=(150, 98, 58), outline=ink)
    for cx in (310, 458):
        d.ellipse((cx - 62, 240, cx + 62, 364), fill=(255, 255, 255), outline=ink, width=5)
        d.ellipse((cx - 26, 276, cx + 26, 328), fill=ink)
    d.polygon([(384, 350), (360, 395), (408, 395)], fill=(240, 170, 40), outline=ink)  # beak
    d.ellipse((170, 470, 260, 780), fill=(150, 98, 58), outline=ink, width=5)        # wings
    d.ellipse((508, 470, 598, 780), fill=(150, 98, 58), outline=ink, width=5)
    for cx in (320, 448):
        d.ellipse((cx - 55, 870, cx + 55, 925), fill=(240, 170, 40), outline=ink, width=4)  # feet
    img.save(path)


def draw_robot(path):
    img = Image.new("RGB", (768, 1024), (245, 247, 250))
    d = ImageDraw.Draw(img)
    ink = (30, 35, 45)
    d.rounded_rectangle((234, 430, 534, 760), 30, fill=(90, 150, 220), outline=ink, width=6)  # torso
    d.rounded_rectangle((274, 190, 494, 380), 30, fill=(140, 190, 240), outline=ink, width=6)  # head
    d.rectangle((354, 380, 414, 430), fill=(120, 120, 130), outline=ink, width=4)            # neck
    d.line((384, 190, 384, 80), fill=ink, width=4)                                           # antenna
    d.ellipse((370, 64, 398, 92), fill=(230, 60, 60), outline=ink)
    for cx in (334, 434):
        d.ellipse((cx - 28, 250, cx + 28, 306), fill=(255, 230, 80), outline=ink, width=4)  # eyes
        d.rounded_rectangle((cx - 40, 760, cx + 40, 930), 25, fill=(120, 120, 130), outline=ink, width=5)
    d.line((234, 470, 160, 700), fill=ink, width=40)                                         # arms
    d.line((534, 470, 608, 700), fill=ink, width=40)
    d.ellipse((600, 200, 680, 280), fill=(250, 200, 50), outline=ink, width=5)               # floating orb
    img.save(path)


def main():
    SKETCH_DIR.mkdir(parents=True, exist_ok=True)
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    draw_owl(SKETCH_DIR / "owl.png")
    draw_robot(SKETCH_DIR / "robot.png")

    owl = sdf_to_mesh(owl_sdf, (-1.6, -1.6, -0.3), (1.6, 1.6, 3.7))
    robot = sdf_to_mesh(robot_sdf, (-1.8, -1.8, -0.4), (1.8, 1.8, 3.7), n=150)
    for name, mesh in (("owl", owl), ("robot", robot)):
        mesh.export(MESH_DIR / f"{name}.stl")
        parts = len(mesh.split(only_watertight=False))
        print(f"{name}: {len(mesh.faces):,} faces, watertight={mesh.is_watertight}, parts={parts}")


if __name__ == "__main__":
    main()
