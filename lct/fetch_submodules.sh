#!/usr/bin/env bash
# Fetch all submodules (recursively).
#
# External hosts (RWTH GitLab, gitlab.com for Eigen, ...) are often slow or
# down for CI runners, so the populated submodule tree is cached as a
# pre-release asset "deps-<hash of submodule pins>" in this repository. Only
# when the pins change (upstream update) do we fetch from the network, and the
# result is uploaded for the next builds.
set -u

KEY=$(git ls-tree -r HEAD | awk '$2=="commit" {print $3, $4}' | sort | git hash-object --stdin | cut -c1-12)
TAG="deps-$KEY"
echo "== submodule cache key: $TAG"
if [ -n "${GH_TOKEN:-}" ] && gh release download "$TAG" -p deps.tar.gz -O deps.tar.gz --clobber 2>/dev/null; then
  echo "== using cached submodules from release $TAG"
  tar -xzf deps.tar.gz && rm -f deps.tar.gz
  exit 0
fi
echo "== no cache, fetching submodules from the network"

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

# Eigen: gitlab.com is often overloaded -> GitHub mirror if gitlab does not answer
if ! reach "https://gitlab.com/libeigen/eigen.git"; then
  git config --global "url.https://github.com/libigl/eigen.git.insteadOf" "https://gitlab.com/libeigen/eigen.git"
fi

git submodule sync --recursive
annotate() {  # show the tail of a log as one error annotation (raw logs are hard to reach)
  printf '::error title=%s::%s\n' "$1" "$(tail -n 25 "$2" | sed 's/%/%25/g' | awk '{printf "%s%%0A", $0}')"
}
populated() {  # submodule dir has real content (not only the .git link file)
  [ -n "$(ls -A "$1" 2>/dev/null | grep -v '^\.git$')" ]
}

PATHS=$(git config -f .gitmodules --get-regexp '\.path$' | awk '{print $2}')
for p in $PATHS; do
  ok=0
  for attempt in 1 2 3; do
    if [ "$attempt" -eq 1 ]; then depth="--depth 1"; else depth=""; fi
    if git submodule update --init --recursive $depth -- "$p" > sub.log 2>&1 && populated "$p"; then
      ok=1; break
    fi
    cat sub.log
    echo "== $p: attempt $attempt failed, retrying"
    sleep $((attempt * 10))
  done
  if [ "$ok" -ne 1 ]; then
    annotate "submodule $p" sub.log
    exit 1
  fi
done
git submodule status --recursive

# upload the populated tree for the next builds (parallel jobs may race: ignore)
if [ -n "${GH_TOKEN:-}" ]; then
  tar --exclude='.git' -czf deps.tar.gz $(git config -f .gitmodules --get-regexp '\.path$' | awk '{print $2}') \
    && (gh release view "$TAG" >/dev/null 2>&1 || gh release create "$TAG" deps.tar.gz --prerelease \
          --title "Build cache $KEY" --notes "Submodule sources for CI builds (GPL/BSD/MPL sources of the dependencies)." ) \
    || echo "== cache upload skipped"
  rm -f deps.tar.gz
fi
