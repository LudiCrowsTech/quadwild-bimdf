"""Print build errors from build.log as one GitHub Actions error annotation."""
import os
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "build.log"
if not os.path.isfile(path):
    sys.exit(0)
lines = open(path, errors="replace").read().splitlines()
hits = [l for l in lines if re.search(r"(error|ERROR|undefined reference|fatal|FAILED)", l)]
body = hits[:40] or lines[-40:]
print("::error title=build.log::" + "%0A".join(l.replace("%", "%25")[:300] for l in body))
