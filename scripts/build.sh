#!/usr/bin/env bash
# build.sh - get the engine this project was measured on and build it for this GPU.
#
# Strata ships prebuilt binaries for common cards; there was none for v0.1.45 on an
# RTX 4050 Laptop (sm_89), so the engine is compiled from source. This script records
# exactly that path so a reader can reproduce it.
#
# Env: CUDA_DIR (default /usr/local/cuda-12.8), CUDA_ARCH (default 89), REV (default 477ac13c...)
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CUDA_DIR="${CUDA_DIR:-/usr/local/cuda-12.8}"
CUDA_ARCH="${CUDA_ARCH:-89}"
REV="${REV:-477ac13cbe8e582c20484871ce459d20d82df09d}"   # v0.1.45, the commit this repo was measured on
                                                        # (verify: git -C Strata describe --tags -> v0.1.45)

if [ ! -d "$ROOT/Strata/.git" ]; then
    echo "cloning Strata into $ROOT/Strata"
    git clone https://github.com/Niko1221/Strata "$ROOT/Strata"
fi
cd "$ROOT/Strata"

# A checkout may be shallow, or may have been fetched past $REV, so the commit is not
# guaranteed to be local. Resolve it explicitly instead of letting `git checkout` fail
# with a bare pathspec error.
if ! git rev-parse --verify --quiet "${REV}^{commit}" >/dev/null; then
    echo "rev $REV is not in this checkout; fetching it"
    git fetch --tags origin "$REV" 2>/dev/null \
        || git fetch --tags --unshallow origin 2>/dev/null \
        || git fetch --tags origin
fi
git rev-parse --verify --quiet "${REV}^{commit}" >/dev/null \
    || { echo "cannot resolve REV=$REV in $ROOT/Strata — pass a valid commit, e.g. REV=$(git rev-parse HEAD)" >&2; exit 1; }

# Detach: a branch pointer (main) can move under us, a commit cannot. Note that Strata's
# documented update flow is `git pull` + update.sh, which needs a branch — run
# `git checkout main` (or pass REV=main) if you want to track upstream instead of this pin.
git checkout --detach "$REV"
echo "engine source: $(git rev-parse --short HEAD) ($(git describe --tags --always 2>/dev/null || echo no-tag)) — detached, pinned to this commit"
echo "  to track upstream instead: git -C '$ROOT/Strata' checkout main"

# Optional: keep a 66 GB download inside a 4 MiB/s link limit. Harmless if already applied.
if [ -f "$ROOT/download-throttle.patch" ]; then
    git apply --check "$ROOT/download-throttle.patch" 2>/dev/null \
        && git apply "$ROOT/download-throttle.patch" \
        || echo "patch already applied (or upstream changed); continuing"
fi

# The documented setup path (creates .venv, downloads weights, prepares the pack).
./setup.sh --model Q2_0 --context 32768 --vision no --low-ram mmap \
    --data-dir "${DATA_DIR:-$ROOT/Strata-data}" --no-start --yes

# For reference, the exact engine build setup used here (setup.sh runs this itself):
#   cmake -G Ninja -S Strata -B Strata/build -DCMAKE_BUILD_TYPE=Release \
#     -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
#     -DSTRATA_Q6K_EXPERTS=ON -DSTRATA_MMQ_KQUANTS=ON \
#     -DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCH \
#     -DCMAKE_CUDA_COMPILER=$CUDA_DIR/bin/nvcc -DCUDAToolkit_ROOT=$CUDA_DIR \
#     -DSTRATA_GGML_DIR=Strata/third_party/llama.cpp
#   cmake --build Strata/build --target strata -j 6

echo "engine built: $ROOT/Strata/engine/strata"
echo "run it with: $ROOT/scripts/run.sh"
