#!/usr/bin/env bash
# Show the instruction at the address where the kernel logged a trap: trap_disasm.sh <binary> <hex file offset> <label>
f=$1; off=$((16#$2))
read seg_off seg_va <<<"$(readelf -lW "$f" | awk '$1=="LOAD" && / R E / {print $2, $3; exit}')"
va=$(( off - seg_off + seg_va ))
printf '=== %s\n%s, file offset 0x%x = address 0x%x' "$3" "$f" "$off" "$va"
sym=$(addr2line -f -e "$f" "$(printf '0x%x' "$va")" 2>/dev/null | head -1 | c++filt)
echo "  (function: ${sym:-unknown})"
objdump -d -M intel --start-address=$((va-40)) --stop-address=$((va+10)) "$f" \
  | grep -E '^\s+[0-9a-f]+:' | tail -8 | sed "s/^\( *$(printf '%x' "$va"):\)/>>>\1/"
echo
