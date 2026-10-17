#!/usr/bin/env bash
# run.sh - start the tuned Strata server used for every measurement in this repo.
#
# The config is generated from config/strata-q2_0.json.template so that the paths and
# the tuning flags are explicit in one place (Methodology §3 of the README) instead of
# buried in an absolute path written by setup.sh.
#
# Env: ROOT, DATA_DIR, PORT, CONTEXT, VRAM_RESERVE_MIB, KV_RESIDENT, CONVO_CACHE_MIB, CUDA_DIR
#
# Examples:
#   ./scripts/run.sh                                  # this box: :8097, 131k context
#   PORT=8080 CONTEXT=16384 ./scripts/run.sh          # a cleaner/similar box
#   CONVO_CACHE_MIB=0 ./scripts/run.sh                # parking off, to reproduce run 1/2
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${DATA_DIR:-$ROOT/Strata-data}"
PORT="${PORT:-8097}"
CONTEXT="${CONTEXT:-131072}"
VRAM_RESERVE_MIB="${VRAM_RESERVE_MIB:-512}"
KV_RESIDENT="${KV_RESIDENT:-20480}"
CONVO_CACHE_MIB="${CONVO_CACHE_MIB:-1024}"
CUDA_DIR="${CUDA_DIR:-/usr/local/cuda-12.8}"

[ -x "$ROOT/Strata/engine/strata" ] || { echo "engine not built. run ./scripts/build.sh first" >&2; exit 1; }
[ -d "$DATA_DIR/packs/q2_0" ] || { echo "no pack at $DATA_DIR/packs/q2_0. run ./scripts/build.sh first" >&2; exit 1; }

config="$ROOT/config/strata-q2_0.json"
mkdir -p "$ROOT/config" "$ROOT/logs"
sed -e "s|{{ROOT}}|$ROOT|g" \
    -e "s|{{DATA_DIR}}|$DATA_DIR|g" \
    -e "s|{{PORT}}|$PORT|g" \
    -e "s|{{CONTEXT}}|$CONTEXT|g" \
    -e "s|{{VRAM_RESERVE_MIB}}|$VRAM_RESERVE_MIB|g" \
    -e "s|{{KV_RESIDENT}}|$KV_RESIDENT|g" \
    -e "s|{{CONVO_CACHE_MIB}}|$CONVO_CACHE_MIB|g" \
    -e "s|{{CUDA_DIR}}|$CUDA_DIR|g" \
    "$ROOT/config/strata-q2_0.json.template" > "$config"

echo "config: $config"
echo "  context=$CONTEXT  kv=int8  kv-resident=$KV_RESIDENT  vram-reserve=$VRAM_RESERVE_MIB MiB"
echo "  parking=$CONVO_CACHE_MIB MiB  mmap experts  no --mtp  spec 4"
echo "loading the model: the first start takes a minute or two, and the machine may stall for 1-3 minutes"
echo "then: curl -s http://127.0.0.1:$PORT/health"

exec "$ROOT/Strata/.venv/bin/python" "$ROOT/Strata/serve/server.py" \
    --engine strata --config "$config" --port "$PORT"
