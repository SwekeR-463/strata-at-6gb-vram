# LOG — how this box got here

The running record of the experiment. For the design, the tuning and the measurements read the
[README](README.md); for per-task numbers read [results.md](results.md). Timestamps are IST.

## Timeline

- **2026-10-17 14:47** — setup started. Engine compiling from source (~10–50 min), then the 66.4 GB
  download (~2 h at this box's measured ~8 MB/s), then pack preparation.
- **2026-10-17 19:55** — setup finished (`rc=0`): both shards, 31.6 GiB expert pack, dense pack, MTP
  draft, `run-q2_0.sh`. Transcript: `logs/setup-q2_0-20261017.log`.
- **2026-10-17 21:10** — **first successful run**: ~9 tok/s decode, ~16–25 tok/s prefill,
  85 MB/token from SSD, 25–30% cache hit. Server live on :8097.
- **2026-10-17 21:35** — optimization round: spec 6 / kv q4_0 / adapt-async / prefill CPU share all
  ≈neutral or worse (Methodology §4); **short-python-v1 suite: 6/6** at 9.3–10.0 tok/s. Biggest
  remaining lever: the `tern` app holding 892 MiB of VRAM.
- **2026-10-17 22:45** — `tern` closed; the freed VRAM reinvested. **64k then 131k context live** via
  KV streaming (`--kv-resident 32768`, 1.55 GiB pinned): expert cache 344 → **599 slots**, decode
  8.3–9.6 tok/s, prefill 18.4 tok/s, cache hit 51.6% on a warm request. Suite re-run at 131k: **6/6**
  at **7.40 tok/s** — the honest price of context is **−24%**, not the ~10% spot samples suggested.
- **2026-10-17 23:02** — **Pi wired to this server** as a custom provider and driven end to end: the
  177B located, read, edited and verified a real bug fix in 5 turns (4 `tool_calls` + a clean stop),
  including a working `edit` tool call.
- **2026-10-18 00:02** — **prefill round.** Found the real limiter: every prompt chunk is a full pass
  over the 31 GB expert set (the engine's "492 µs per missed expert" *is* the read time), so prefill
  = `ceil(prompt/chunk)` passes of ~25 GB at ~1.9 GB/s. Retuned VRAM (`--vram-reserve-mib 512`,
  `--kv-resident` to its 20,480 minimum) → **chunk 512 → 1280, cache 599 → 856 slots**, cold prefill
  **41.6 → 51–54 tok/s** (+23–30%). Rejected `--expert-cache-per-layer` (neutral: our cache is
  profile-filled, not arrival-order) and `--resident-cpu-experts` (engine declines it; swap hit 100%).
- **2026-10-18 00:20** — **conversation parking enabled** (`--conversation-cache-mib 1024
  --conversation-cache-slots 4 --conversation-cache-min-tokens 128 --conversation-cache-park-gain
  512`). Parking is off by default, and it is the difference that matters for an agent: a cold
  5.2k-token turn costs 107 s, and every turn after it **1–2 s** (5,208 of 5,229 prompt tokens reused)
  instead of another 107 s. ~429 MB of parked RAM per 5.2k conversation; `park-gain 512` stops each
  turn from writing a fresh snapshot (3 evictions of the 1,024 MiB budget in 3 turns without it).
- **2026-10-18 00:10** — **short-python-v1 re-run at 131k on the retuned config: 6/6 at 7.81 tok/s**
  (run 2: 7.40), all `finish_reason=stop`, 4,317 generated tokens. The +5.5% is the bigger cache (856
  slots, ~50% hit rate inside a request vs ~44% at 599 slots).

## Open items

- **Run 1 vs run 2 is not a clean A/B.** ~80 min and a long session apart; a back-to-back 16k/131k
  run would separate the KV-mode cost from thermal drift.
- **`--vram-reserve-mib 512` is the risky part.** The engine's #2065 warning says 262 MiB free. If
  decode ever collapses, raise it toward 896 and re-measure the cache/chunk loss.
- **Cross-engine comparison** — a `docs/studies/` page in the `local=lm` workbench putting this run
  next to the llama.cpp CPU-MoE numbers (Gemopus-4-26B 5/6, KAT-Coder V2.5 4/6) on the same box.
- **PLE table** — the output-side n-gram lookup is read unbuffered (`--ple-io direct`) and is drawn
  in the data path but never profiled separately. Worth a `stream-stat.sh` run isolated to it.

## Fallbacks (same model only)

The rule for this project is one model: **Qwen3.8-Flash-Next**, any quant of it. If Strata stops
working, these are the arms — never a different model.

1. **llama.cpp** — `TheTom/llama-cpp-turboquant` has `qwen4exp` in its model registry; run the same
   standard GGUF with mmap + `--n-cpu-moe` + TurboQuant KV types. No adaptive expert cache; same
   page-cache SSD streaming.
2. **Gyro-S TQ1_0** — agentionai quant, 27.64 GiB weights (~1.34 bpw) but AGP rotors mean stock
   llama.cpp cannot load it; needs agentionai/llama.cpp or Strata-rc2 (CUDA/Vulkan).
3. **Custom, if required** — page-cache warmers (`posix_fadvise WILLNEED` over hot expert ranges),
   prefetch shaping, VFS tunables (needs root; not available on this box).
