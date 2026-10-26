"""Print build errors from build.log as GitHub Actions error annotations."""
import os
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "build.log"
if not os.path.isfile(path):
    sys.exit(0)
lines = open(path, errors="replace").read().splitlines()
pat = re.compile(r"(CMake Error|error|Error|ERROR|undefined reference|fatal|FAILED)")
blocks = []
for i, l in enumerate(lines):
    if pat.search(l):
        blocks.append("\n".join(lines[i:i + 6]))
    if len(blocks) >= 8:
        break
if not blocks:
    blocks = ["\n".join(lines[-40:])]
for b in blocks:
    msg = b.replace("%", "%25").replace("\r", "").replace("\n", "%0A")[:2000]
    print("::error title=build.log::" + msg)
