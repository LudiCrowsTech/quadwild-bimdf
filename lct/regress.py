#!/usr/bin/env python3
"""Regression test for the QuadWild engine binaries. Stdlib only.

Runs the same 2-step pipeline the Blender add-on runs, on a few generated
test meshes, and writes metrics.json. Success is judged by OUTPUT FILES,
never by exit code (Windows builds return garbage exit codes); the exit
codes are only logged.

Usage:
  python3 regress.py --bin <dir with quadwild + quad_from_patches>
                     --config <engine config dir> --out metrics.json
                     [--commit SHA] [--baseline old_metrics.json]
Exit code 1 if any mesh fails or a baseline comparison fails.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_test_meshes  # noqa: E402

TIMEOUT = 300
QUAD_TARGET = 1000     # "num" argument of quad_from_patches
SCALE = "1.5"
MIN_QUAD_PCT = 95.0
MAX_IRREG_RISE = 1.30  # baseline check
MAX_TIME_RATIO = 2.5


def exe(bin_dir, name):
    for cand in (name + ".exe", name):
        p = os.path.join(bin_dir, cand)
        if os.path.isfile(p):
            return os.path.abspath(p)
    raise FileNotFoundError("%s not found in %s" % (name, bin_dir))


def run(cmd, cwd):
    """Run a command with timeout. Returns (returncode or None on timeout)."""
    try:
        r = subprocess.run(cmd, cwd=cwd, timeout=TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        tail = r.stdout.decode("utf-8", "replace")[-1500:]
        return r.returncode, tail
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT after %d s" % TIMEOUT


def make_main_txt(config_dir, dest, scale):
    src = os.path.join(config_dir, "main_config", "flow_noalign_lemon.txt")
    flow = os.path.abspath(os.path.join(config_dir, "main_config", "flow_virtual_simple.json"))
    sats = os.path.abspath(os.path.join(config_dir, "satsuma", "lemon.json"))
    lines = []
    with open(src) as f:
        for line in f:
            s = line.strip()
            if s.startswith("flow_config_filename"):
                line = 'flow_config_filename "%s"\n' % flow.replace("\\", "/")
            elif s.startswith("satsuma_config_filename"):
                line = 'satsuma_config_filename "%s"\n' % sats.replace("\\", "/")
            elif s.startswith("scaleFact"):
                line = "scaleFact %s\n" % scale
            lines.append(line)
    with open(dest, "w", newline="\n") as f:
        f.writelines(lines)


def analyze_obj(path):
    """Return (faces, quad_pct, irregular) for an OBJ with tri/quad/ngon faces."""
    faces = []
    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("f "):
                ids = [int(t.split("/")[0]) for t in line.split()[1:]]
                if len(ids) >= 3:
                    faces.append(ids)
    if not faces:
        return 0, 0.0, 0
    quads = sum(1 for f in faces if len(f) == 4)
    edge_count = {}
    neighbors = {}
    for f in faces:
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            key = (a, b) if a < b else (b, a)
            edge_count[key] = edge_count.get(key, 0) + 1
            neighbors.setdefault(a, set()).add(b)
            neighbors.setdefault(b, set()).add(a)
    boundary = set()
    for (a, b), c in edge_count.items():
        if c == 1:
            boundary.add(a)
            boundary.add(b)
    irregular = sum(1 for v, nb in neighbors.items()
                    if v not in boundary and len(nb) != 4)
    return len(faces), 100.0 * quads / len(faces), irregular


def run_mesh(name, mesh_path, bins, config_dir):
    res = {"ok": False, "faces": 0, "quad_pct": 0.0, "irregular": 0,
           "seconds": 0.0, "field_rc": None, "quad_rc": None}
    quadwild, qfp = bins
    work = tempfile.mkdtemp(prefix="lct_%s_" % name)
    try:
        shutil.copy(mesh_path, os.path.join(work, "work.obj"))
        with open(os.path.join(work, "prep.txt"), "w", newline="\n") as f:
            f.write("do_remesh 1\nsharp_feature_thr -1\nalpha 0.01\nscaleFact 1\n")
        with open(os.path.join(work, "work.sharp"), "w", newline="\n") as f:
            f.write("0\n")
        make_main_txt(config_dir, os.path.join(work, "main.txt"), SCALE)

        t0 = time.time()
        rc, out = run([quadwild, "work.obj", "2", "prep.txt", "work.sharp"], work)
        res["field_rc"] = rc
        print("  [%s] quadwild rc=%s" % (name, rc))
        patched = os.path.join(work, "work_rem_p0.obj")
        if not os.path.isfile(patched):
            print("  [%s] FAIL: work_rem_p0.obj missing\n%s" % (name, out))
            return res
        rc, out = run([qfp, "work_rem_p0.obj", str(QUAD_TARGET), "main.txt", "stats.json"], work)
        res["quad_rc"] = rc
        res["seconds"] = round(time.time() - t0, 2)
        print("  [%s] quad_from_patches rc=%s" % (name, rc))

        base = "work_rem_p0_%d_quadrangulation" % QUAD_TARGET
        result = None
        for cand in (base + "_smooth.obj", base + ".obj"):
            p = os.path.join(work, cand)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                result = p
                break
        if result is None:
            print("  [%s] FAIL: no quadrangulation output\n%s" % (name, out))
            return res
        faces, qpct, irr = analyze_obj(result)
        res.update(faces=faces, quad_pct=round(qpct, 2), irregular=irr)
        res["ok"] = faces > 0 and qpct >= MIN_QUAD_PCT
        if not res["ok"]:
            print("  [%s] FAIL: faces=%d quad_pct=%.1f" % (name, faces, qpct))
    except Exception as e:  # keep going with other meshes
        print("  [%s] ERROR: %r" % (name, e))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return res


def compare(meshes, baseline):
    ok = True
    print("\n%-14s %9s %9s %9s %9s %s" % ("mesh", "irr", "irr_base", "sec", "sec_base", "verdict"))
    for name, m in meshes.items():
        b = baseline.get("meshes", {}).get(name)
        if not b or not b.get("ok"):
            print("%-14s %9s %9s %9s %9s %s" % (name, m["irregular"], "-", m["seconds"], "-", "no baseline"))
            continue
        bad = []
        if m["irregular"] > b["irregular"] * MAX_IRREG_RISE and m["irregular"] > b["irregular"]:
            bad.append("irregular +30%")
        if b["seconds"] > 0 and m["seconds"] > b["seconds"] * MAX_TIME_RATIO:
            bad.append("time x2.5")
        if bad:
            ok = False
        print("%-14s %9s %9s %9s %9s %s" % (name, m["irregular"], b["irregular"], m["seconds"],
                                           b["seconds"], "FAIL: " + ", ".join(bad) if bad else "ok"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="metrics.json")
    ap.add_argument("--commit", default="")
    ap.add_argument("--baseline")
    a = ap.parse_args()

    bins = (exe(a.bin, "quadwild"), exe(a.bin, "quad_from_patches"))
    mesh_dir = tempfile.mkdtemp(prefix="lct_meshes_")
    sys.argv = [sys.argv[0], mesh_dir]
    make_test_meshes.main()

    meshes = {}
    for fn in sorted(os.listdir(mesh_dir)):
        if fn.endswith(".obj"):
            name = fn[:-4]
            print("== %s" % name)
            meshes[name] = run_mesh(name, os.path.join(mesh_dir, fn), bins, a.config)
    shutil.rmtree(mesh_dir, ignore_errors=True)

    metrics = {"platform": "%s-%s" % (platform.system().lower(), platform.machine().lower()),
               "meshes": meshes}
    if a.commit:
        metrics["commit"] = a.commit
    with open(a.out, "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n%-14s %4s %7s %8s %9s %8s %9s %8s" % (
        "mesh", "ok", "faces", "quad%", "irregular", "seconds", "field_rc", "quad_rc"))
    for n, m in meshes.items():
        print("%-14s %4s %7d %8.1f %9d %8.1f %9s %8s" % (
            n, "yes" if m["ok"] else "NO", m["faces"], m["quad_pct"], m["irregular"],
            m["seconds"], m["field_rc"], m["quad_rc"]))

    good = bool(meshes) and all(m["ok"] for m in meshes.values())
    if a.baseline:
        with open(a.baseline) as f:
            good = compare(meshes, json.load(f)) and good
    print("\nRESULT: %s" % ("PASS" if good else "FAIL"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
