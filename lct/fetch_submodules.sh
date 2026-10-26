#!/usr/bin/env bash
# Fetch all submodules (recursively), redirecting the RWTH GitLab host
# (www.graphics.rwth-aachen.de:9000, often unreachable from CI runners) to a
# reachable mirror with global "insteadOf" rules, so nested submodules (e.g.
# OpenMesh's own cmake-library) are redirected too.
set -u

RWTH="https://www.graphics.rwth-aachen.de:9000/"
CMAKE_GH="https://github.com/cgg-bern/cmake-library.git"

# 'timeout' is missing on stock macOS
if command -v timeout >/dev/null 2>&1; then TO="timeout 60"; elif command -v gtimeout >/dev/null 2>&1; then TO="gtimeout 60"; else TO=""; fi
reach() { $TO git ls-remote "$1" HEAD >/dev/null 2>&1; }

BASE=""
for b in "$RWTH" "https://gitlab.vci.rwth-aachen.de:9000/" "https://graphics.rwth-aachen.de:9000/"; do
  echo "== probing $b"
  if reach "${b}OpenMesh/OpenMesh.git" && reach "${b}CoMISo/CoMISo.git"; then BASE="$b"; break; fi
done
if [ -z "$BASE" ]; then
  echo "::error::No reachable host for OpenMesh/CoMISo (RWTH GitLab)."
  exit 1
fi
echo "== using $BASE for RWTH submodules"
if [ "$BASE" != "$RWTH" ]; then
  git config --global "url.${BASE}.insteadOf" "$RWTH"
fi

# cmake-library: RWTH copy if reachable, else the GitHub copy
if ! reach "${BASE}cmake/cmake-library.git"; then
  echo "== cmake-library: using $CMAKE_GH"
  git config --global --add "url.${CMAKE_GH}.insteadOf" "${RWTH}cmake/cmake-library.git"
  git config --global --add "url.${CMAKE_GH}.insteadOf" "${BASE}cmake/cmake-library.git"
fi

git submodule sync --recursive
if ! git submodule update --init --recursive --depth 1; then
  echo "== shallow fetch failed, retrying full"
  git submodule update --init --recursive || exit 1
fi
git submodule status --recursive
