# strata-at-6gb-vram

Out-of-tree experiment, deliberately **separate from the `local=lm` workbench**: run
Qwen3.8-Flash-Next on the RTX 4050 Laptop (6 GB VRAM) + 15 GB RAM box through Strata's
SSD-streaming low-RAM mode.

## Rules

- **One model only: Qwen3.8-Flash-Next** (any quant of it: ISTA GSQ-RCO, Gyro, Unsloth).
  Never substitute another model, even if smaller.
- Keep everything in this directory: engine in `Strata/`, model data in `Strata-data/`,
  tools in `tools/`, JSON results in `results/`.
- This box is **below Strata's minimums** (6 GB vs 12 GB VRAM; 15 GB vs 32 GB RAM).
  Never trust defaults here; every claim needs measurement:
  `tools/stream-stat.sh` (SSD bytes/token, swap, page faults) and `tools/bench-strata.py`.
- Results are machine-readable JSON including the model ID, the exact engine args, the
  engine/commit revision, and the setup transcript reference.
- `Strata-data/` is huge and resumable: never re-download shards that are present.
- Swap is ~100% used and there is no sudo: no assumptions that extra swap or kernel
  tuning is available.

## Where things are

- `README.md` - goal, quick start, **Methodology** (data path + mermaid, what Strata does vs what
  we changed, rejected levers, how each number was measured, limits), results
- `LOG.md` - the running record: timeline, open items, fallbacks (same model only)
- `results.md` - short-python-v1 per-task tables; `results/` - raw JSON/CSV of every run
- `scripts/build.sh` / `scripts/run.sh` - reproduce the exact stack (engine rev `b95137167bd9b751`,
  tuned flags from `config/strata-q2_0.json.template`)
- `data/MANIFEST.json` - the model files every measurement used (102 GB, not in the repo)
- `logs/` - setup transcript and server console (evidence); `docs/strata-engine-help.txt` - engine flag reference
- `Strata/` - the engine checkout (gitignored, upstream MIT); `Strata-data/` - shards, packs, MTP (gitignored)
