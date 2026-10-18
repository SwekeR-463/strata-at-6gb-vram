# Credits and attribution

This repo is a measurement record, not an engine. Split it cleanly:

## Upstream — everything that makes the model run at all

**Strata**, [github.com/Niko1221/Strata](https://github.com/Niko1221/Strata), MIT license,
Copyright (c) 2026 Niko1221 and contributors. Built here at commit
**`477ac13cbe8e582c20484871ce459d20d82df09d`** (tag `v0.1.45`) for `sm_89` / CUDA 12.8.

The design decisions that make a 177B MoE fit in 6 GB of VRAM belong to Strata, not to this
project: the tiered adaptive expert cache, mmap expert streaming, the CPU pool that computes
missed experts in place, KV streaming, prompt-lookup/suffix drafting, the routing-frequency
expert profile, and conversation parking as a mechanism. See Methodology §2 of the README for
which of those are running at their defaults.

**Model weights:** ISTA-DASLab `Qwen3.8-Flash-Next-GSQ-RCO-GGUF` (Q2_0), under their own terms.
Not redistributed here — see `data/MANIFEST.json`.

**Reference configs:** the Reddit thread
[*QFN Q_2 strata configs for 8gb vram and 32gb ram*](https://www.reddit.com/r/LocalLLaMA/comments/1x5p822/),
which this project measures against.

## This project — the deltas and the measurements

- The below-minimum setup decision and the from-source build for `sm_89`.
- `download-throttle.patch` (downloader capped at 3.5 MiB/s).
- The context ladder: `--max-context` 32k → 16k → 65k → 131k via `--kv int8 --kv-resident`.
- The VRAM retune: `--vram-reserve-mib 512`, `--kv-resident` at its 20,480 minimum.
- Enabling conversation parking with `--conversation-cache-park-gain 512`.
- Dropping `--mtp`.
- The tooling: `tools/bench-strata.py`, `tools/reuse-test.py`, `tools/stream-stat.sh`.
- Every number in `README.md`, `results.md` and `results/`.

Everything measured is reproducible from `scripts/build.sh` + `scripts/run.sh`, and the rejected
levers are listed in Methodology §4 with their null results.
