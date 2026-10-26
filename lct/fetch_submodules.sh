#!/usr/bin/env bash
# Fetch all submodules, trying mirrors for the ones hosted on the RWTH GitLab
# (www.graphics.rwth-aachen.de:9000 is often unreachable from CI runners).
set -u

git submodule init

# Candidate URLs per submodule path (first that answers wins).
# Plain function instead of associative arrays: macOS ships bash 3.2.
candidates() {
  case "$1" in
    cmake-library) echo "https://www.graphics.rwth-aachen.de:9000/cmake/cmake-library.git https://gitlab.vci.rwth-aachen.de:9000/cmake/cmake-library.git https://github.com/cgg-bern/cmake-library.git" ;;
    libs/OpenMesh) echo "https://www.graphics.rwth-aachen.de:9000/OpenMesh/OpenMesh.git https://gitlab.vci.rwth-aachen.de:9000/OpenMesh/OpenMesh.git https://graphics.rwth-aachen.de:9000/OpenMesh/OpenMesh.git" ;;
    libs/CoMISo)   echo "https://www.graphics.rwth-aachen.de:9000/CoMISo/CoMISo.git https://gitlab.vci.rwth-aachen.de:9000/CoMISo/CoMISo.git https://graphics.rwth-aachen.de:9000/CoMISo/CoMISo.git" ;;
  esac
}

# 'timeout' is missing on stock macOS
if command -v timeout >/dev/null 2>&1; then TO="timeout 60"; elif command -v gtimeout >/dev/null 2>&1; then TO="gtimeout 60"; else TO=""; fi

for path in cmake-library libs/OpenMesh libs/CoMISo; do
  name=$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk -v p="$path" '$2==p {print $1}' | sed 's/^submodule\.//; s/\.path$//')
  ok=0
  for url in $(candidates "$path"); do
    echo "== $path: trying $url"
    if $TO git ls-remote "$url" HEAD >/dev/null 2>&1; then
      git config "submodule.$name.url" "$url"
      echo "== $path: using $url"
      ok=1
      break
    fi
  done
  if [ "$ok" -ne 1 ]; then
    echo "::error::No reachable source for submodule $path"
    exit 1
  fi
done

# Fetch everything (retry once: hosts can be flaky)
git submodule update --recursive --depth 1 || git submodule update --recursive
git submodule status
