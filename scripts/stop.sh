#!/usr/bin/env bash
# stop.sh - stop the Strata server that run.sh started, and the engine with it.
#
# run.sh execs Strata/serve/server.py, which owns the engine as a child, so terminating
# the process listening on PORT is enough: the engine exits with it. Ctrl-C in a
# foreground run.sh does the same thing.
#
# It refuses to kill a listener that is not the Strata server, so PORT=8080 on this box
# (SearXNG) or any other accidental port is a no-op rather than a surprise.
#
# Env: PORT (default 8097), TIMEOUT (seconds to wait after SIGTERM, default 30)
set -euo pipefail

PORT="${PORT:-8097}"
TIMEOUT="${TIMEOUT:-30}"

listening() { ss -lntH "sport = :$PORT" 2>/dev/null | grep -q .; }

pids="$(ss -lntpH "sport = :$PORT" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true)"

if [ -z "$pids" ]; then
    echo "nothing listening on :$PORT"
    # An engine can outlive its server only if the server was killed with -9.
    if pgrep -x strata >/dev/null 2>&1; then
        echo "  but an engine process is still running: $(pgrep -x strata | tr '\n' ' ')"
        echo "  it is safe to kill: pkill -x strata"
    fi
    exit 0
fi

# Safety: never kill a listener we did not start.
for p in $pids; do
    cmd="$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | sed 's/ $//')"
    case "$cmd" in
        *serve/server.py*) ;;
        *) echo "refusing to kill pid $p on :$PORT - not the Strata server:" >&2
           echo "  $cmd" >&2
           exit 2 ;;
    esac
done

echo "stopping the Strata server on :$PORT (pid $(echo "$pids" | tr '\n' ' '))"
kill $pids

for _ in $(seq 1 "$TIMEOUT"); do
    listening || break
    sleep 1
done

if listening; then
    echo "  :$PORT still listening after ${TIMEOUT}s; sending SIGKILL" >&2
    kill -9 $pids 2>/dev/null || true
    sleep 2
fi

if listening; then
    echo "  :$PORT IS STILL LISTENING - check by hand: ss -lntp 'sport = :$PORT'" >&2
    exit 1
fi
echo "  :$PORT free"

if pgrep -x strata >/dev/null 2>&1; then
    echo "  the engine is still up; stopping it too"
    pkill -x strata || true
    sleep 2
fi
if pgrep -x strata >/dev/null 2>&1; then
    echo "  engine STILL running: pid $(pgrep -x strata | tr '\n' ' ')" >&2
else
    echo "  engine stopped"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
    echo "  GPU now: $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader)"
fi
echo "  RAM now: $(free -m | awk 'NR==2 {printf "%d MiB used, %d MiB available", $3, $7}') | swap: $(free -m | awk 'NR==3 {printf "%d MiB used", $3}')"
