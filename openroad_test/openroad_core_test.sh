#!/usr/bin/env bash
# Per-core CPU test with a fixed OpenROAD computation (Linux, x86-64).
#
#   ./openroad_core_test.sh              cores 0 and 6, three runs each, alternating (about 10 minutes)
#   ./openroad_core_test.sh 0 1 2 3      chosen cores, one run each
#   ./openroad_core_test.sh all          every core once (about 2-3 minutes per core)
#
# The same single-threaded job (clock-tree synthesis of a saved chip layout) runs pinned to one core at a time. It is
# deterministic: on a healthy core every run finishes in about two minutes with a byte-identical result. Needs about
# 8 GB of free RAM, `taskset` (util-linux) and either Nix or the exact OpenROAD build below. Run it on an otherwise idle
# machine at default BIOS settings, so the tested core reaches its normal boost clock.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OPENROAD=/nix/store/2y36a4sr078y15ick388dncqjdzmlxga-openroad-2026-02-17
CACHE=https://nix-cache.fossi-foundation.org
KEYS="cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= nix-cache.fossi-foundation.org:3+K59iFwXqKsL7BNu6Guy0v+uTlwsxYQxjspXzqLYQs="
EXPECTED=3b15a48370b9f8d8535bb8f96c1193ef4c04ba2e1e59ee29057516ad61a56f76   # SHA-256 of the result (out/snn2_d.odb) on a healthy core

# 1. Get the exact OpenROAD build (33 MB download from the public FOSSi Foundation binary cache).
if [ ! -x "$OPENROAD/bin/openroad" ]; then
    if ! command -v nix-store > /dev/null; then
        echo "OpenROAD is fetched with Nix. Install it (single-user, about 2 minutes), then run this script again:"
        echo "    sh <(curl -L https://nixos.org/nix/install) --no-daemon && . ~/.nix-profile/etc/profile.d/nix.sh"
        exit 2
    fi
    nix-store --realise "$OPENROAD" --option substituters "https://cache.nixos.org $CACHE" \
        --option trusted-public-keys "$KEYS" > /dev/null || { echo "Could not fetch OpenROAD"; exit 2; }
fi

# 2. Which cores.
ncpu=$(nproc --all)
if [ "${1:-}" = all ]; then cores=$(seq 0 $((ncpu - 1)))
elif [ $# -gt 0 ]; then cores="$*"
else cores="0 6 0 6 0 6"; fi

echo "CPU: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | sed 's/^ //')"
echo "Microcode: $(grep -m1 microcode /proc/cpuinfo | awk '{print $3}'), kernel $(uname -r)"
for c in $(printf '%s\n' $cores | sort -nu); do
    f=/sys/devices/system/cpu/cpu$c/cpufreq
    [ -r $f/scaling_max_freq ] && echo "core $c: maximum clock $(( $(cat $f/scaling_max_freq) / 1000 )) MHz" \
        "(hardware maximum $(( $(cat $f/cpuinfo_max_freq) / 1000 )) MHz)"
done
echo

# 3. Run.
WORK=$(mktemp -d "${TMPDIR:-/tmp}/cpu-core-test.XXXXXX")
tar -xJf "$HERE/cts_bundle.tar.xz" -C "$WORK"
LOG="$HERE/results_$(date +%Y%m%d_%H%M%S).txt"
declare -A runs=() bad=()
n=0
for core in $cores; do
    n=$((n + 1))
    d="$WORK/run${n}_core$core"
    cp -a "$WORK/cts_bundle" "$d" && mkdir -p "$d/out"
    t0=$(date +%s)
    (cd "$d" && PATH="$OPENROAD/bin:$PATH" timeout 900 taskset -c "$core" ./run.sh > log.txt 2>&1)
    rc=$?
    secs=$(( $(date +%s) - t0 ))
    sig=$(grep -o -m1 'Signal [0-9]* received' "$d/log.txt" | awk '{print $2}')
    if [ -n "$sig" ]; then result="CRASH ($( [ "$sig" = 11 ] && echo 'segmentation fault' || \
        { [ "$sig" = 4 ] && echo 'illegal instruction' || echo "signal $sig"; } ))"
    elif [ $rc -eq 0 ] && [ "$(sha256sum < "$d/out/snn2_d.odb" | cut -c1-64)" = "$EXPECTED" ]; then result="ok"
    elif [ $rc -eq 0 ]; then result="WRONG RESULT $(sha256sum < "$d/out/snn2_d.odb" | cut -c1-16)"
    elif [ $rc -eq 124 ]; then result="HANG (timeout)"
    else result="FAILED (exit code $rc)"; fi
    printf 'run %2d  core %2d  %-30s %4d s\n' $n "$core" "$result" $secs | tee -a "$LOG"
    runs[$core]=$(( ${runs[$core]:-0} + 1 ))
    if [ "$result" = ok ]; then rm -rf "$d"
    else bad[$core]=$(( ${bad[$core]:-0} + 1 )); cp "$d/log.txt" "$HERE/failed_run${n}_core${core}.log"; rm -rf "$d"; fi
done
rm -rf "$WORK"

echo | tee -a "$LOG"
echo "core  runs  failed" | tee -a "$LOG"
for c in $(printf '%s\n' "${!runs[@]}" | sort -n); do
    printf '%4d  %4d  %6d\n' "$c" "${runs[$c]}" "${bad[$c]:-0}" | tee -a "$LOG"
done
echo "Results: $LOG"
