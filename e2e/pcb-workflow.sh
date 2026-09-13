#!/usr/bin/env bash
# Prove that this consumer resolves and deterministically exports the in-review
# hardware-engineer PCB workflow. This does not execute workflow nodes.
set -eu

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
outfitter_bin="$repo_root/node_modules/.bin/outfitter"
test_root=$(mktemp -d "${TMPDIR:-/tmp}/outfitter-pcb-workflow.XXXXXX")
cleanup() { rm -rf -- "$test_root"; }
trap cleanup EXIT HUP INT TERM

mkdir -p "$test_root/home" "$test_root/system"
test -x "$outfitter_bin" || {
  echo "missing pinned Outfitter CLI; run 'npm ci' first" >&2
  exit 1
}

run_outfitter() {
  HOME="$test_root/home" \
    XDG_CONFIG_HOME="$test_root/home/.config" \
    OUTFITTER_SYSTEM_DIR="$test_root/system" \
    "$outfitter_bin" "$@"
}

cd "$repo_root"

run_outfitter sync --strict
run_outfitter validate --strict

agents_json=$(run_outfitter list agents --strict --json)
workflows_json=$(run_outfitter list workflows --strict --json)
node -e '
  const [agents, workflows] = process.argv.slice(1).map(value => JSON.parse(value).resources);
  const expected = "github:ai-outfitter/community-profiles#feat/pcb-supplier-quote";
  const agent = agents.find(value => value.slug === "hardware-engineer");
  const workflow = workflows.find(value => value.slug === "pcb-design");
  if (!agent) throw new Error("hardware-engineer is not resolvable");
  if (!workflow) throw new Error("pcb-design is not enabled");
  if (agent.layer !== expected) throw new Error(`hardware-engineer resolved from ${agent.layer}`);
  if (workflow.layer !== expected) throw new Error(`pcb-design resolved from ${workflow.layer}`);
' "$agents_json" "$workflows_json"

first="$test_root/first"
second="$test_root/second"
run_outfitter dump --workflow pcb-design --strict --out "$first"
run_outfitter dump --workflow pcb-design --strict --out "$second"
diff -ru "$first" "$second"

node e2e/assert-pcb-workflow.mjs "$first"

echo "PASS  hardware-engineer and pcb-design resolve from the review pin"
echo "PASS  pcb-design exports are byte-identical"
echo "PASS  setup and supplier-quote skills, MCPs, dependencies, and typed outputs are present"
