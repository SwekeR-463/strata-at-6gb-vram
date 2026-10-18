#!/usr/bin/env python3
"""bench-strata.py - minimal benchmark for a running Strata server (OpenAI-compatible API).

Usage:
  tools/bench-strata.py [--base-url http://127.0.0.1:8080] [--out results/bench.json] [--wait 600]

Three requests against /v1/chat/completions, temperature 0:
  1. long prompt (~--fill-tokens), max_tokens=1   -> prefill rate
  2. same long prompt, max_tokens=N              -> decode rate after a long prefill
  3. short prompt, max_tokens=N                  -> decode rate from a warm short prompt

Rates come from the server's own `timings` block when present (Strata returns
predicted_per_second / prompt_per_second, which exclude prefill from decode);
otherwise they fall back to wall-clock tokens/second over the whole request.

Request 2 deliberately does NOT subtract request 1's wall time. At these settings
request 2 reuses request 1's prefix, so it does not pay that prefill at all, and the
subtraction therefore compared unrelated numbers: it went negative and the clamp
turned it into a nonsense "34000 tok/s" in results/bench-20261017-firstrun.json.

Samples MemAvailable/swap around the run. Everything is stdlib.

Machine-readable output includes the model ID, per the workbench convention.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def post(url, payload, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    return body, time.time() - t0


def get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_health(base, seconds):
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            get(base + "/health")
            return True
        except Exception:
            time.sleep(3)
    return False


def sample_mem():
    out = {}
    try:
        with open("/proc/meminfo") as f:
            m = {line.split(":")[0]: line.split(":")[1].strip() for line in f if ":" in line}
        out["mem_available_mib"] = int(m["MemAvailable"].split()[0]) // 1024
        out["swap_used_mib"] = (
            int(m["SwapTotal"].split()[0]) - int(m["SwapFree"].split()[0])
        ) // 1024
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8080")
    ap.add_argument("--model", default="qwen3.8-flash-next-q2_0")
    ap.add_argument("--fill-tokens", type=int, default=1024)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--wait", type=int, default=0, help="seconds to wait for /health first")
    ap.add_argument("--timeout", type=float, default=7200)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    base = a.base_url.rstrip("/")
    if a.wait and not wait_health(base, a.wait):
        print("server not healthy within %ds" % a.wait, file=sys.stderr)
        return 2

    filler = "The quick brown fox jumps over the lazy dog. " * 200
    long_prompt = (
        "Read the following text, then reply with the single word OK.\n\n"
        + (filler * (a.fill_tokens * 4 // len(filler) + 1))[: a.fill_tokens * 4]
    )

    results = {
        "base_url": base,
        "model": a.model,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "protocol": "temperature 0, stream off, wall-clock timed",
        "requests": [],
        "memory": {"before": sample_mem()},
    }
    raw_wall = {}   # name -> unrounded wall seconds

    def run(name, prompt, max_tokens, note):
        body, dt = post(
            base + "/v1/chat/completions",
            {
                "model": a.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,
                "stream": False,
            },
            a.timeout,
        )
        usage = body.get("usage") or {}
        timings = body.get("timings") or {}
        pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
        raw_wall[name] = dt          # unrounded, for every derived rate below
        rec = {
            "name": name,
            "wall_s": round(dt, 3),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "note": note,
        }
        if ct:
            rec["tok_s_end_to_end"] = round(ct / dt, 2)
        if timings:
            rec["timings"] = timings
            if timings.get("predicted_per_second"):
                rec["decode_tok_s_server"] = timings["predicted_per_second"]
            if timings.get("prompt_per_second"):
                rec["prefill_tok_s_server"] = timings["prompt_per_second"]
        results["requests"].append(rec)
        print("%-12s %8.2fs  prompt=%-6s completion=%-5s (%s)" % (name, dt, pt, ct, note))
        return rec

    pre = run("prefill_long", long_prompt, 1, "long prompt, 1 token out")
    dec_long = run("decode_long", long_prompt, a.max_tokens, "same prompt, generate")
    dec_short = run("decode_short", "Write one sentence about the sea.", a.max_tokens, "short prompt")

    if pre.get("prefill_tok_s_server"):
        results["prefill_tok_s"] = pre["prefill_tok_s_server"]
        results["prefill_source"] = "server timings (prompt_per_second)"
    elif pre["prompt_tokens"]:
        results["prefill_tok_s"] = round(pre["prompt_tokens"] / raw_wall["prefill_long"], 1)
        results["prefill_source"] = "wall clock"

    results["decode_source"] = {}
    for key, rec in (("decode_tok_s_after_long_prefill", dec_long),
                     ("decode_tok_s_short_prompt", dec_short)):
        if not rec["completion_tokens"]:
            continue
        if rec.get("decode_tok_s_server"):
            results[key] = rec["decode_tok_s_server"]
            results["decode_source"][key] = "server timings (predicted_per_second)"
        else:
            results[key] = round(rec["completion_tokens"] / raw_wall[rec["name"]], 2)
            results["decode_source"][key] = "wall clock (whole request, all completion tokens)"

    results["memory"]["after"] = sample_mem()
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w") as f:
            json.dump(results, f, indent=2)
        print("wrote", a.out)
    else:
        print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
