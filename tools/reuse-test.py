#!/usr/bin/env python3
"""Agent-shape prefill test: a role-based multi-turn conversation, one request per turn.

Turn 1 is cold -- the engine has to read the whole prompt off the SSD. With conversation
parking on (`--conversation-cache-mib`), every later turn restores the parked K/V and reads
only the new tokens. The engine reports the split per request as

    prompt <N> tokens = <R> reused + <F> read in <T> ms (<X> tok/s)

in its log; this tool prints wall time and prompt tokens per turn, and the engine's own
split when given --log. Compare the same run with parking off (`--conversation-cache-mib 0`)
to see the difference: without it a growing conversation is re-read from the start every turn.

usage:
  tools/reuse-test.py                                  # 4 turns, ~2k-token conversation
  tools/reuse-test.py --turns 3 --repeats 90 --log Strata/strata-q2_0.log
"""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request

BLOCK = (
    "FILE 3 of 12 - module config/loader.py\n"
    "def load(path, strict=True):\n"
    "    raw = open(path).read()\n"
    "    data = json.loads(raw)\n"
    "    return _validate(data, strict)\n"
    "NOTE: the loader normalises keys to lowercase before validation.\n"
    "class Registry:\n"
    "    def __init__(self, entries):\n"
    "        self.entries = {e.name: e for e in entries}\n"
    "RETRY POLICY: three attempts, exponential backoff starting at 250 ms, jitter 20 percent.\n"
)

WORDS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]

REUSE = re.compile(
    r"prompt (?P<prompt>\d+) tokens = (?P<reused>\d+) reused \+ \d+(?: of \d+)? read in (?P<read>[\d.]+) ms"
)


def ask(base_url, model, messages, max_tokens, timeout):
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    ).encode()
    req = urllib.request.Request(base_url + "/v1/chat/completions", body, {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    wall = time.time() - t0
    usage = data.get("usage") or {}
    reply = (data["choices"][0]["message"].get("content") or "").strip()
    return wall, usage.get("prompt_tokens"), usage.get("completion_tokens"), reply


def log_size(log_path):
    try:
        return os.path.getsize(log_path)
    except OSError:
        return 0


def engine_split(log_path, before):
    """The engine's own reused/read accounting for the request that ended after `before`."""
    try:
        with open(log_path, "r", errors="replace") as fh:
            fh.seek(before)
            lines = fh.read().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        m = REUSE.search(line)
        if m:
            return m.groupdict()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8097")
    ap.add_argument("--model", default="qwen3.8-flash-next-q2_0")
    ap.add_argument("--turns", type=int, default=4)
    ap.add_argument("--repeats", type=int, default=45, help="prompt size: how many BLOCKs (45 ~= 5.2k tokens)")
    ap.add_argument("--max-tokens", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--log", default="", help="engine log path, to print its reused/read split per turn")
    a = ap.parse_args()

    big = BLOCK * a.repeats
    system = {"role": "system", "content": "You are a terse file-analysis assistant."}
    history = []
    print("turns=%d  conversation ~%d tokens at the end\n" % (a.turns, (len(big) // 4) + a.turns * 8))
    print("  %-5s %8s %9s %9s  %s" % ("turn", "wall", "prompt", "out", "engine"))
    for i in range(a.turns):
        word = WORDS[i % len(WORDS)]
        messages = [system] + history + [
            {"role": "user", "content": big + "\nReply with the single word: " + word}
        ]
        before = log_size(a.log) if a.log else 0
        wall, pt, ct, reply = ask(a.base_url, a.model, messages, a.max_tokens, a.timeout)
        note = "reply=%r" % reply[:24]
        if a.log:
            split = engine_split(a.log, before)
            if split:
                note = "prompt %s = %s reused + read %s ms" % (
                    split["prompt"], split["reused"], split["read"],
                )
        flag = "cold" if i == 0 else ""
        print("  %-5s %7.1fs %9s %9s  %s %s" % (i + 1, wall, pt, ct, note, flag))
        history += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": "Reply with the single word: " + WORDS[(i + 1) % len(WORDS)]},
        ]
    print(
        "\n  first turn is the cold prompt; later turns should be ~1-2 s with\n"
        "  --conversation-cache-mib set, and as slow as the first without it."
    )


if __name__ == "__main__":
    main()
