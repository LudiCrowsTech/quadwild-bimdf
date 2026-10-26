#!/usr/bin/env python3
"""Generate deterministic closed triangle test meshes (OBJ). Stdlib only.

Usage: python3 make_test_meshes.py <out_dir>
"""
import math
import os
import random
import sys


def _norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)


def icosphere(level=3, radius=1.0):
    t = (1.0 + math.sqrt(5.0)) / 2.0
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
             (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
             (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = [_norm(v) for v in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
             (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
             (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
             (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(level):
        cache = {}
        new_faces = []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = _norm(tuple((verts[a][i] + verts[b][i]) / 2 for i in range(3)))
                verts.append(m)
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new_faces += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new_faces
    return [tuple(c * radius for c in v) for v in verts], faces


def noisy_sphere(seed=1234, amount=0.04):
    rng = random.Random(seed)
    verts, faces = icosphere(3)
    out = []
    for v in verts:
        k = 1.0 + rng.uniform(-amount, amount)
        out.append(tuple(c * k for c in v))
    return out, faces


def torus(major=1.0, minor=0.4, nu=64, nv=32):
    verts, faces = [], []
    for i in range(nu):
        u = 2 * math.pi * i / nu
        for j in range(nv):
            v = 2 * math.pi * j / nv
            r = major + minor * math.cos(v)
            verts.append((r * math.cos(u), r * math.sin(u), minor * math.sin(v)))
    for i in range(nu):
        for j in range(nv):
            a = i * nv + j
            b = ((i + 1) % nu) * nv + j
            c = ((i + 1) % nu) * nv + (j + 1) % nv
            d = i * nv + (j + 1) % nv
            faces += [(a, b, c), (a, c, d)]
    return verts, faces


def rounded_box(n=16, inner=0.6):
    """Cube surface grid projected onto a rounded box (rounded edges/corners)."""
    index, verts, faces = {}, [], []

    def vid(p):
        key = tuple(round(c, 6) for c in p)
        if key not in index:
            q = tuple(max(-inner, min(inner, c)) for c in p)
            d = tuple(p[i] - q[i] for i in range(3))
            dn = _norm(d)
            r = 1.0 - inner
            verts.append(tuple(q[i] + r * dn[i] for i in range(3)))
            index[key] = len(verts) - 1
        return index[key]

    for axis in range(3):
        for sign in (-1.0, 1.0):
            a1, a2 = (axis + 1) % 3, (axis + 2) % 3
            grid = []
            for i in range(n + 1):
                row = []
                for j in range(n + 1):
                    p = [0.0, 0.0, 0.0]
                    p[axis] = sign
                    p[a1] = -1.0 + 2.0 * i / n
                    p[a2] = -1.0 + 2.0 * j / n
                    row.append(vid(p))
                grid.append(row)
            for i in range(n):
                for j in range(n):
                    a, b, c, d = grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]
                    faces += [(a, b, c), (a, c, d)]
    return verts, faces


def orient_outward_star(verts, faces):
    """Flip triangles whose normal points toward the origin (star-shaped meshes)."""
    out = []
    for a, b, c in faces:
        pa, pb, pc = verts[a], verts[b], verts[c]
        u = [pb[i] - pa[i] for i in range(3)]
        v = [pc[i] - pa[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        cen = [(pa[i] + pb[i] + pc[i]) / 3 for i in range(3)]
        out.append((a, b, c) if sum(n[i] * cen[i] for i in range(3)) > 0 else (a, c, b))
    return out


def write_obj(path, verts, faces):
    with open(path, "w", newline="\n") as f:
        for v in verts:
            f.write("v %.6f %.6f %.6f\n" % v)
        for a, b, c in faces:
            f.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    meshes = {
        "icosphere": icosphere(3),
        "torus": torus(),
        "rounded_box": rounded_box(),
        "noisy_sphere": noisy_sphere(),
    }
    for name, (v, f) in meshes.items():
        if name != "torus":  # torus is wound consistently by construction
            f = orient_outward_star(v, f)
        write_obj(os.path.join(out, name + ".obj"), v, f)
        print("%s: %d verts, %d tris" % (name, len(v), len(f)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
