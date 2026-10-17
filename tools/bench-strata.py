#!/usr/bin/env python3
"""bench-strata.py - minimal benchmark for a running Strata server (OpenAI-compatible API).

Usage:
  tools/bench-strata.py [--base-url http://127.0.0.1:8080] [--out results/bench.json] [--wait 600]

Three requests against /v1/chat/completions, temperature 0:
  1. long prompt (~--fill-tokens), max_tokens=1   -> prefill rate
  2. same long prompt, max_tokens=N              -> decode rate after a long prefill
  3. short prompt, max_tokens=N                  -> decode rate from a warm short prompt

Decode rate for (2) subtracts request (1)'s wall time, so the one token that
belongs to the prefill is not counted twice; that makes it slightly
conservative. Samples MemAvailable/swap around the run. Everything is stdlib.

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
        pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
        rec = {
            "name": name,
            "wall_s": round(dt, 3),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "note": note,
        }
        if ct:
            rec["tok_s_end_to_end"] = round(ct / dt, 2)
        results["requests"].append(rec)
        print("%-12s %8.2fs  prompt=%-6s completion=%-5s (%s)" % (name, dt, pt, ct, note))
        return rec

    pre = run("prefill_long", long_prompt, 1, "long prompt, 1 token out")
    dec_long = run("decode_long", long_prompt, a.max_tokens, "same prompt, generate")
    dec_short = run("decode_short", "Write one sentence about the sea.", a.max_tokens, "short prompt")

    if pre["prompt_tokens"] and pre["wall_s"]:
        results["prefill_tok_s"] = round(pre["prompt_tokens"] / pre["wall_s"], 1)
    if dec_long["completion_tokens"]:
        denom = max(0.001, dec_long["wall_s"] - pre["wall_s"])
        results["decode_tok_s_after_long_prefill"] = round((dec_long["completion_tokens"] - 1) / denom, 2)
    if dec_short["completion_tokens"]:
        results["decode_tok_s_short_prompt"] = round(dec_short["completion_tokens"] / dec_short["wall_s"], 2)

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
