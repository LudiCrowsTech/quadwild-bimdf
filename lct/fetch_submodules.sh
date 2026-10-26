#!/usr/bin/env bash
# Fetch all submodules, trying mirrors for the ones hosted on the RWTH GitLab
# (www.graphics.rwth-aachen.de:9000 is often unreachable from CI runners).
set -u

git submodule init

# path -> candidate URLs (first that works wins)
declare -A CANDIDATES
CANDIDATES[cmake-library]="https://www.graphics.rwth-aachen.de:9000/cmake/cmake-library.git https://gitlab.vci.rwth-aachen.de:9000/cmake/cmake-library.git https://github.com/cgg-bern/cmake-library.git"
CANDIDATES[libs/OpenMesh]="https://www.graphics.rwth-aachen.de:9000/OpenMesh/OpenMesh.git https://gitlab.vci.rwth-aachen.de:9000/OpenMesh/OpenMesh.git https://graphics.rwth-aachen.de:9000/OpenMesh/OpenMesh.git"
CANDIDATES[libs/CoMISo]="https://www.graphics.rwth-aachen.de:9000/CoMISo/CoMISo.git https://gitlab.vci.rwth-aachen.de:9000/CoMISo/CoMISo.git https://graphics.rwth-aachen.de:9000/CoMISo/CoMISo.git"

for path in "${!CANDIDATES[@]}"; do
  name=$(git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk -v p="$path" '$2==p {print $1}' | sed 's/^submodule\.//; s/\.path$//')
  ok=0
  for url in ${CANDIDATES[$path]}; do
    echo "== $path: trying $url"
    if timeout 60 git ls-remote "$url" HEAD >/dev/null 2>&1; then
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
