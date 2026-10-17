# Results — Qwen3.8 Flash Next Q2_0, served by Strata on a 6 GB laptop

All numbers below were measured on **this** stack, end to end:

| | |
|---|---|
| Model | **Qwen3.8 Flash Next Q2_0** (ISTA GSQ-RCO GGUF, 2-bit experts), 2 shards, 66.4 GB — the only model used in this project |
| Engine | **[Strata](https://github.com/Niko1221/Strata) 0.1.45** — built from source for `sm_89` / CUDA 12.8 (no prebuilt binary for v0.1.45), expert profile + adaptive expert cache |
| Serving | Strata's OpenAI-compatible server, `127.0.0.1:8097/v1` — `--mmap-experts` (experts read from the file tier), `--kv int8`, KV streamed via `--kv-resident`, `--prefill auto`, `--spec 4` |
| Hardware | RTX 4050 Laptop, **6 GB VRAM**, 15.6 GB RAM, NVMe measured at ~1.9 GB/s |
| Harness | `local=lm` → `scripts/benchmark-code.sh`, suite **short-python-v1** |
| Protocol | greedy — `temperature 0`, `reasoning_effort low`, `max_tokens 1024`, `seed 42` |
| Grading | 6 Python tasks; the code block is extracted from the reply, executed, and its output compared against the expected result |

**What is being attributed.** These numbers characterise the whole stack — **Strata's engine
design** as configured for a 6 GB card: SSD-streamed experts, the tiered adaptive expert cache, KV
streaming, and the CPU pool that computes missed experts. Running a 177B MoE with ~10 of 24,576
experts per token on 6 GB of VRAM is only possible because of that design; the architecture is
Strata's. The tuning deltas layered on top (context ladder, `--vram-reserve-mib` / `--kv-resident`
retune, conversation parking, no `--mtp`) are this project's and are described in the
[README](README.md). The tests exercise Strata's OpenAI-compatible surface exactly as a real
client would.

## 6/6 in all three runs

### Run 1 — 16k context, KV fully in VRAM (2026-10-17 21:38 IST, 344 expert slots)

| Task | Result | Gen tokens | Decode |
|---|---|---:|---:|
| merge-intervals | PASS | 632 | 9.3 tok/s |
| binary-metrics | PASS | 814 | 9.6 tok/s |
| flatten-dict | PASS | 645 | 9.9 tok/s |
| dependency-order | PASS | 762 | 10.0 tok/s |
| parse-env | PASS | 664 | 10.0 tok/s |
| batch-iterable | PASS | 630 | 9.5 tok/s |
| **Total** | **6/6** | 4,147 | **9.72 avg** |

### Run 2 — 131k context, KV streamed (2026-10-17 22:59 IST, 599 expert slots)

| Task | Result | Gen tokens | Decode |
|---|---|---:|---:|
| merge-intervals | PASS | 632 | 7.6 tok/s |
| binary-metrics | PASS | 857 | 7.5 tok/s |
| flatten-dict | PASS | 722 | 7.4 tok/s |
| dependency-order | PASS | 854 | 7.5 tok/s |
| parse-env | PASS | 667 | 7.2 tok/s |
| batch-iterable | PASS | 646 | 7.2 tok/s |
| **Total** | **6/6** | 4,378 | **7.40 avg** |

### Run 3 — 131k context, retuned VRAM and parking on (2026-10-18 00:10 IST, 856 expert slots)

| Task | Result | Gen tokens | Decode |
|---|---|---:|---:|
| merge-intervals | PASS | 630 | 8.1 tok/s |
| binary-metrics | PASS | 852 | 7.1 tok/s |
| flatten-dict | PASS | 683 | 8.1 tok/s |
| dependency-order | PASS | 839 | 8.2 tok/s |
| parse-env | PASS | 667 | 7.8 tok/s |
| batch-iterable | PASS | 646 | 7.8 tok/s |
| **Total** | **6/6** | 4,317 | **7.81 avg** |

## Summary

| Run | Context | KV | Expert slots | Result | Generated | Decode avg |
|---|---|---:|---:|---|---:|---:|
| 1 | 16k | fully resident | 344 | **6/6** | 4,147 | **9.72 tok/s** |
| 2 | 131k | streamed, `--kv-resident 32768` | 599 | **6/6** | 4,378 | **7.40 tok/s** |
| 3 | 131k | streamed, `--kv-resident 20480` + parking | 856 | **6/6** | 4,317 | **7.81 tok/s** |

The "decode avg" above is **token-weighted** (total generated tokens ÷ total generation time),
which is the figure the runs are compared on. The unweighted mean of the six per-task rates is
9.72 / 7.40 / **7.85** — runs 1 and 2 agree under both conventions, run 3 differs only in the
second decimal, and the +5.5% comparison holds either way (7.40 → 7.81 or 7.85).

**The honest price of context is −24%** (9.72 → 7.40 tok/s), measured with the identical protocol.
Spot samples had suggested only ~0.5–1 tok/s; the suite is the number to trust. Caveat: run 1 was
~80 min earlier in a long session, so part of the gap may be thermal drift rather than the KV
mode — a back-to-back A/B would separate them.

**Run 3 is +5.5% over run 2 on the same protocol**, and the delta is the larger expert cache
(599 → 856 slots; ~50% vs ~44% in-request hit rate). It is an apples-to-apples comparison: the
harness continues a capped generation with a follow-up request, and those legs reused the prefix in
run 2 as well (615 of 633 prompt tokens), because the engine still holds the slot for the request
that immediately preceded. Parking is what makes that reuse survive a gap or another conversation
in between, not what enables a continuation.

No truncations in any run: every task finished with `finish_reason=stop`, all well under the
1,024-token cap.

## Raw runs

| Run | Raw run (workbench) | Summary copy (here) |
|---|---|---|
| 1 (16k) | `local=lm/results/short-python-qwen38-flash-next-q2_0-20261017-213012/` | `results/short-python-qwen38-flash-next-q2_0-16k-20261017.json` |
| 2 (131k) | `local=lm/results/short-python-qwen38-flash-next-q2_0-20261017-224746/` | `results/short-python-qwen38-flash-next-q2_0-131k-20261017.json` |
| 3 (131k retuned) | `local=lm/results/short-python-qwen38-flash-next-q2_0-20261017-235955/` | `results/short-python-qwen38-flash-next-q2_0-131k-retuned-20261018.json` |

Each raw directory holds the per-task request JSON, response, extracted candidate, evaluation
output and a `summary.json`.

## Reproduce

Without the workbench (stdlib only, no external harness):

```bash
./scripts/run.sh                                   # start the tuned server (:8097)
./tools/bench-strata.py --base-url http://127.0.0.1:8097 --wait 600 --out results/bench.json
./tools/reuse-test.py --base-url http://127.0.0.1:8097 --turns 4 --log logs/strata-q2_0.log
./tools/stream-stat.sh <pid> 2 300               # SSD bytes/token, RSS, swap, faults, VRAM
```

With the `local=lm` workbench (the harness these runs used; the workbench inherits HOST/PORT, so
the suite runs against the Strata server instead of starting its own engine):

```bash
HOST=127.0.0.1 PORT=8097 scripts/benchmark-code.sh qwen38-flash-next-q2_0
```

Requires the Strata server live (`curl -s http://127.0.0.1:8097/health`) and the model profile
`config/models/qwen38-flash-next-q2_0.env` with a machine override setting `PORT="8097"`.
Raw run directories live in the workbench's `results/`; the summary copies are in this repo.
