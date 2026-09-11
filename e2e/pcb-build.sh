#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
board="$repo_root/hardware/pnb-1"
python="$repo_root/hardware/.venv/bin/python"

test -x "$python" || {
  echo "missing PCB virtual environment; run npm run pcb:setup" >&2
  exit 1
}

mkdir -p "$board/review" "$board/fab"
cd "$board"

"$python" -m compileall -q pnb1_skidl.py schematic.py verify.py build.py route.py verify_margins.py package_manifest.py
"$python" verify.py --selftest | tee review/verify-selftest.log
"$python" verify_margins.py | tee review/margins.log

if PNB_FAULT=short-3v3-to-sda "$python" pnb1_skidl.py >review/fault-injection.log 2>&1; then
  echo "fault injection unexpectedly passed" >&2
  exit 1
fi
sed -i "s|$repo_root|<repo>|g" review/fault-injection.log
grep -Eq 'Pin conflict|SKiDL ERC not clean' review/fault-injection.log

"$python" pnb1_skidl.py | tee review/schematic-gate.log
"$python" build.py | tee review/build.log
"$python" route.py | tee review/route.log
"$python" -m kibot -b pnb-1.kicad_pcb -c pnb-1.kibot.yaml -d fab
sed -i 's/[[:space:]]*$//' pnb-1.net fab/bom.csv
kicad-cli pcb render --side top --width 1600 --height 1100 -o fab/front.png pnb-1.kicad_pcb
kicad-cli pcb render --side bottom --width 1600 --height 1100 -o fab/back.png pnb-1.kicad_pcb

cd "$repo_root"
XDG_CACHE_HOME="$repo_root/.pcb-cache" node e2e/kicad-mcp-smoke.mjs \
  hardware/pnb-1 hardware/pnb-1/review/toolchain.json
"$python" hardware/pnb-1/package_manifest.py --write
