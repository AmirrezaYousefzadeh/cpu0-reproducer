#!/usr/bin/env bash
# Per-core CPU test: compile the same C file (SQLite 3.50.4, public domain) with gcc, pinned to one core at a time.
#
#   ./gcc_core_test.sh                 cores 0 and 6, 2 minutes each, twice, alternating (about 8 minutes)
#   ./gcc_core_test.sh 0 1 2 3         chosen cores, 2 minutes each
#   ./gcc_core_test.sh all             every core, 1 minute each
#   SECONDS_PER_CORE=300 ./gcc_core_test.sh 0 6
#
# On a healthy processor every compile succeeds and produces the same object file on every core. A crash of the
# compiler ("internal compiler error: Segmentation fault / Illegal instruction") or a different object file means
# that core computed something wrong. Needs gcc, unzip, taskset and sha256sum (Ubuntu: sudo apt install gcc unzip).
# Run it on an otherwise idle machine at default BIOS settings, so the tested core reaches its normal boost clock.
# Each result line shows the core's average clock while compiling; other busy programs lower it.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SRC_ZIP="$HERE/sqlite-amalgamation-3500400.zip"
SRC_SHA256=1d3049dd0f830a025a53105fc79fd2ab9431aea99e137809d064d8ee8356b032
for tool in gcc unzip taskset sha256sum; do
    command -v $tool > /dev/null || { echo "Missing $tool (Ubuntu: sudo apt install gcc unzip)"; exit 2; }
done
[ "$(sha256sum < "$SRC_ZIP" | cut -c1-64)" = "$SRC_SHA256" ] || { echo "Source archive checksum mismatch"; exit 2; }

ncpu=$(nproc --all)
if [ "${1:-}" = all ]; then cores=$(seq 0 $((ncpu - 1))); per=${SECONDS_PER_CORE:-60}
elif [ $# -gt 0 ]; then cores="$*"; per=${SECONDS_PER_CORE:-120}
else cores="0 6 0 6"; per=${SECONDS_PER_CORE:-120}; fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/gcc-core-test.XXXXXX")
sampler=""
trap 'kill $sampler 2> /dev/null; rm -rf "$WORK"' EXIT
unzip -q -j "$SRC_ZIP" '*/sqlite3.c' -d "$WORK"
LOG="$HERE/gcc_results_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "CPU: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ //'), microcode" \
         "$(grep -m1 microcode /proc/cpuinfo | awk '{print $3}'), kernel $(uname -r)"
    echo "Compiler: $(gcc --version | head -1)"
    for c in $(printf '%s\n' $cores | sort -nu); do
        f=/sys/devices/system/cpu/cpu$c/cpufreq
        [ -r $f/scaling_max_freq ] && echo "core $c: maximum clock $(( $(cat $f/scaling_max_freq) / 1000 )) MHz" \
            "(hardware maximum $(( $(cat $f/cpuinfo_max_freq) / 1000 )) MHz)"
    done
    echo "Each line: one ${per}-second block of repeated compiles pinned to one core."
    echo
} | tee "$LOG"

declare -A total=() failed=()
hashes="$WORK/hashes"
: > "$hashes"
for core in $cores; do
    end=$(( $(date +%s) + per )); n=0; bad=0; first=""
    f=/sys/devices/system/cpu/cpu$core/cpufreq/cpuinfo_avg_freq
    [ -r "$f" ] || f=/sys/devices/system/cpu/cpu$core/cpufreq/scaling_cur_freq
    ( while :; do cat "$f" 2> /dev/null; sleep 1; done ) > "$WORK/clock" & sampler=$!
    while [ "$(date +%s)" -lt "$end" ]; do
        n=$((n + 1))
        if taskset -c "$core" gcc -O2 -frandom-seed=1 -c "$WORK/sqlite3.c" -o "$WORK/out.o" 2> "$WORK/err.txt"; then
            echo "$core $(sha256sum < "$WORK/out.o" | cut -c1-16)" >> "$hashes"
        else
            bad=$((bad + 1))
            msg=$(grep -m1 'internal compiler error' "$WORK/err.txt" | sed "s|$WORK/||")
            [ -n "$msg" ] || msg=$(tail -1 "$WORK/err.txt")
            [ -z "$first" ] && first=$msg
            echo "  core $core compile $n: ${msg:-gcc failed}" >> "$LOG"
        fi
        rm -f "$WORK/out.o"
    done
    kill $sampler; wait $sampler 2> /dev/null
    mhz=$(awk '$1 > 1000000 {s += $1; k++} END {if (k) printf "%d", s / k / 1000; else printf "?"}' "$WORK/clock")
    total[$core]=$(( ${total[$core]:-0} + n )); failed[$core]=$(( ${failed[$core]:-0} + bad ))
    printf 'core %2d: %3d compiles, %3d failed, average clock %4s MHz  %s\n' "$core" "$n" "$bad" "$mhz" \
        "${first:+(e.g. $first)}" | tee -a "$LOG"
done

# Object files must be identical everywhere; the most common hash is taken as correct.
ref=$(awk '{print $2}' "$hashes" | sort | uniq -c | sort -rn | awk 'NR==1{print $2}')
echo | tee -a "$LOG"
echo "core  compiles  crashed  wrong output" | tee -a "$LOG"
for c in $(printf '%s\n' "${!total[@]}" | sort -n); do
    wrong=$(awk -v c="$c" -v r="$ref" '$1==c && $2!=r' "$hashes" | wc -l)
    printf '%4d  %8d  %7d  %12d\n' "$c" "${total[$c]}" "${failed[$c]}" "$wrong" | tee -a "$LOG"
done
echo "Full log: $LOG"
