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
- **2026-10-18 00:10** — **short-python-v1 re-run at 131k on the retuned config: 6/6 at 7.81 tok/s**
  (run 2: 7.40), all `finish_reason=stop`, 4,317 generated tokens. The +5.5% is the bigger cache (856
  slots, ~50% hit rate inside a request vs ~44% at 599 slots).
- **2026-10-18 00:20** — **conversation parking enabled** (`--conversation-cache-mib 1024
  --conversation-cache-slots 4 --conversation-cache-min-tokens 128 --conversation-cache-park-gain
  512`). Parking is off by default, and it is the difference that matters for an agent: a cold
  5.2k-token turn costs 107 s, and every turn after it **1–2 s** (5,208 of 5,229 prompt tokens reused)
  instead of another 107 s. ~429 MB of parked RAM per 5.2k conversation; `park-gain 512` stops each
  turn from writing a fresh snapshot (3 evictions of the 1,024 MiB budget in 3 turns without it).

- **2026-10-18 14:04** — **review repairs to the packaged repo** (nothing about the engine or the
  tuning changed; the running server was stopped before these edits). Two defects found while
  reviewing the refactor:
  1. **The "engine revision" was never a revision.** `b95137167bd9b751` had been copied out of
     `Strata/engine/BUILD.json`'s `"src"` field, which is a 16-hex sha256 fingerprint of the engine
     sources (`setup.py:source_hash()`, the `git pull` staleness check for upstream issue #31), not
     a commit. It resolved nowhere — not in the local checkout, and GitHub answered 422 "No commit
     found". `scripts/build.sh` therefore could not check it out, breaking the documented reproduce
     path. Replaced everywhere with the real commit `477ac13cbe8e582c20484871ce459d20d82df09d`
     (tag `v0.1.45`), and `build.sh` now fetches a missing rev, detaches, and fails loudly instead
     of dying on a bare pathspec error.
  2. **`tools/bench-strata.py` could report a nonsense decode rate.** It subtracted request 1's
     wall time from request 2 and clamped the denominator, so the shipped first run recorded
     `34000.0 tok/s`. The two requests were not comparable (request 2 reuses request 1's prefix and
     pays no prefill). Rates now come from the server's own `timings` block, with a wall-clock
     fallback that counts all completion tokens and never clamps. The old value is annotated
     in place in `results/bench-20261017-firstrun.json`; no headline number changes.
  3. Units disclaimers, a stale tool default and the `results/` provenance fields are **still
     open** — see Open items.

- **2026-10-18 14:25** — **repo shared, then the remaining open items closed.** Pushed to the private remote
  (`origin`, branch `main`), then:
  1. **Units declared.** `data/MANIFEST.json`'s `total_disk_footprint_gb: 96` — a figure that was
     really 101.9 GB *or* 94.9 GiB depending on which unit you assumed — is now a
     `total_disk_footprint` block carrying `bytes`, `gb_decimal`, `gib`, the measured on-disk value
     and the excluded 6.93 GB MTP draft. README states the convention and labels the figures.
  2. **`tools/bench-strata.py` defaults to `:8097`** like everything else; the README example no
     longer has to pass `--base-url`.
  3. **`results/` provenance.** All nine JSONs now carry the engine revision — the four raw curl
     captures and the bench file got a `_provenance` block, the summary's `engine` block got
     `revision`/`tag`, and the three suite runs also name their own config (`--max-context`, plus
     `kv_resident` where it applied) with a pointer to where that config is recorded. Verified
     byte-for-byte that no measured value changed.
  4. **`EXPERT_PROFILE` is now real.** The README had documented an env var `run.sh` never read.
     The template takes `{{EXPERT_PROFILE}}`, `run.sh` defaults it to
     `Strata/data/expert-profile.bin` and fails loudly if it is missing.
  5. **`scripts/stop.sh`** — stops the server on `PORT` and the engine with it, refuses to kill a
     listener that is not Strata (so `PORT=8080`, which is SearXNG here, is a no-op), and reports
     the GPU/RAM it handed back. `LOG.md`'s `00:10` entry was also filed after `00:20`; fixed.

- **2026-10-19 15:45** — **full-repo review; six corrections, no measurement changed.** Audited
  every tracked file against the raw results and fixed what did not reconcile:
  1. **Footprint arithmetic.** README §1 said "~96 GB (63 GB of GGUFs + a 33 GB prepared pack)" and
     "a ~63 GB model"; the files are 66.4 GB of GGUFs + 35.5 GB of packs = **101.9 GB (94.9 GiB)**.
     Corrected to agree with `data/MANIFEST.json` and the quick start.
  2. **Prefill claim narrowed.** "51–54 tok/s" was the best two of five cold runs. The five are
     **41.7 / 48.5 / 50.2 / 50.9 / 51.7 tok/s** at 1,843 tokens plus **53.9** at 6,422. Now stated as
     **48–54 tok/s, five runs**. Delta 5's "+23–30%" becomes "+16–29%" (41.7 → 48.5–53.9).
  3. **`summary-20261017-firstrun.json` had no `_provenance`** — the only `results/` file that broke
     AGENTS.md's rule. Added (`model_id`, engine revision/tag, setup transcript, config pointer).
  4. **`server_model_redaction` notes removed** from the three suite JSONs: they described a
     home-prefix scrub that the shipped transcript (255 × `/home/sweker`) contradicts. `server_model`
     stays repo-relative.
  5. **MTP draft corrected.** It was downloaded to `Strata-data/mtp` (6.93 GB), never used, and has
     since been deleted; README said "~5 GB" and `MANIFEST` described it as present. Both now say
     downloaded / unused / deleted. `expert_profile.bytes` filled (196,632) and a `sum_scope` note
     makes the total's scope explicit.
  6. **Small alignments.** `results.md` RAM figure 15.6 GB → 15.3 GiB (16 GB installed); the suite
     console trace `results/short-python-console-20261017.log` is now tracked as evidence; the
     redundant manual `git clone` block in the quick start is gone (`build.sh` already clones/pins);
     the per-task file names in the suite JSONs are explained as living in the workbench, not here.

  Verified after the edits: all 9 JSONs parse, all scripts pass `bash -n` / `py_compile`, 0 broken
  internal links, no secrets in tracked text, transcript still byte-identical (blob `a36d8bb`, md5
  `368d8552…`). No measured value changed.

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
