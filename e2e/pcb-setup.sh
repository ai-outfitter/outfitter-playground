#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
venv="$repo_root/hardware/.venv"

cd "$repo_root"
if [ ! -x "$venv/bin/python" ]; then
  uv venv "$venv" --python "$(command -v python3)"
fi
uv pip install --python "$venv/bin/python" -r hardware/requirements-pcb.txt

site_packages=$(
  "$venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])'
)
printf '%s\n' "$PYTHONPATH" | tr ':' '\n' > "$site_packages/nix-kicad.pth"

kicad-cli version
"$venv/bin/python" -c 'import pcbnew, skidl, kinet2pcb; print(f"pcbnew {pcbnew.Version()}")'
"$venv/bin/python" -m kibot --version
easyeda2kicad --help >/dev/null
echo "easyeda2kicad available"
command -v freerouting >/dev/null
echo "freerouting available"
ngspice -v >/dev/null
npx -y kicad-mcp@0.1.6 --version
