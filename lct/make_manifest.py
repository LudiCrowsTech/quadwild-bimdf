#!/usr/bin/env python3
"""Write manifest.json for the Blender add-on. Stdlib only.

The macOS universal zip is listed under both macos-arm64 and macos-x64.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

ZIPS = {  # platform key(s) -> zip file name
    "win-x64": "ariadne-engine-win-x64.zip",
    "linux-x64": "ariadne-engine-linux-x64.zip",
    "macos-arm64": "ariadne-engine-macos-universal.zip",
    "macos-x64": "ariadne-engine-macos-universal.zip",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--commit", required=True)
    ap.add_argument("--upstream-commit", required=True)
    ap.add_argument("--assets-dir", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--out", default="manifest.json")
    a = ap.parse_args()

    platforms = {}
    for plat, name in ZIPS.items():
        path = os.path.join(a.assets_dir, name)
        if not os.path.isfile(path):
            print("missing asset: %s" % path, file=sys.stderr)
            return 1
        platforms[plat] = {
            "url": "https://github.com/%s/releases/download/%s/%s" % (a.repo, a.tag, name),
            "sha256": sha256(path),
        }
    manifest = {"engine": {
        "version": a.version,
        "adapter": 1,
        "notes": a.notes,
        "commit": a.commit,
        "upstream_commit": a.upstream_commit,
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platforms": platforms,
    }}
    with open(a.out, "w", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
