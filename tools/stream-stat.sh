#!/usr/bin/env bash
# stream-stat.sh - sample a running Strata process for SSD-streaming evidence.
#
# Usage: tools/stream-stat.sh <pid> [interval_seconds] [samples]   (0 samples = until stopped)
#
# Emits CSV to stdout:
#   ts,elapsed_s,rss_mib,swap_mib,majflt,minflt,disk_read_mib,disk_read_delta_mib,vram_mib
#
# disk_read_* comes from /proc/<pid>/io read_bytes: bytes actually fetched from
# storage (page-cache hits are excluded). That is the metric that matters when the
# experts stream from the SSD: bytes_read / tokens_generated.
set -euo pipefail

pid="${1:?usage: stream-stat.sh <pid> [interval_seconds] [samples]}"
interval="${2:-2}"
samples="${3:-0}"

[ -d "/proc/$pid" ] || { echo "no such pid: $pid" >&2; exit 1; }

stat_field() { awk -v f="$2" '{print $f}' "/proc/$pid/stat"; }
status_kib()  { awk -v k="$2" '$1==k":" {print $2; exit}' "/proc/$pid/status"; }

echo "ts,elapsed_s,rss_mib,swap_mib,majflt,minflt,disk_read_mib,disk_read_delta_mib,vram_mib"
prev_bytes=0
start=$(date +%s)
i=0
while :; do
    [ -d "/proc/$pid" ] || { echo "# process $pid exited" >&2; break; }

    now=$(date +%s)
    bytes=$(awk '/^read_bytes:/ {print $2}' "/proc/$pid/io" 2>/dev/null || echo 0)
    rss=$(status_kib status VmRSS || echo 0)
    vswap=$(status_kib status VmSwap || echo 0)
    minflt=$(stat_field stat 10)
    majflt=$(stat_field stat 12)
    vram=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null \
           | awk -F', ' -v p="$pid" '$1==p {gsub(/ MiB/,"",$2); print $2; exit}')

    delta=$(( bytes - prev_bytes )); prev_bytes=$bytes
    printf '%s,%d,%.1f,%.1f,%s,%s,%.1f,%.1f,%s\n' \
        "$(date -Is)" "$(( now - start ))" \
        "$(awk -v b="$rss" 'BEGIN{print b/1024}')" \
        "$(awk -v b="$vswap" 'BEGIN{print b/1024}')" \
        "$majflt" "$minflt" \
        "$(awk -v b="$bytes" 'BEGIN{print b/1048576}')" \
        "$(awk -v b="$delta" 'BEGIN{print b/1048576}')" \
        "${vram:-}"

    i=$(( i + 1 ))
    { [ "$samples" -gt 0 ] && [ "$i" -ge "$samples" ]; } && break
    sleep "$interval"
done
