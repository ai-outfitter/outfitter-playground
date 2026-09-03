#!/usr/bin/env bash
# Demo/test the engineer flow on your host — no container. Runs Outfitter
# under a persistent, isolated HOME in /tmp so harness state (logins,
# onboarding, the synced catalog) survives between runs without touching
# your real ~. The repo checkout is reset each run so the seeded bug is
# back and old demo branches are gone.
#
# usage: e2e/demo.sh [pi|claude|codex]  launch the engineer session (default: claude)
#        e2e/demo.sh check              free sanity check: no model calls
#        e2e/demo.sh reset              wipe the demo HOME for a from-scratch start
#
# env: PLAYGROUND_HOME  demo HOME (default /tmp/outfitter-playground-home)
#      ANTHROPIC_API_KEY / OPENAI_API_KEY are passed through when set.
#
# Credentials: your Claude Code / Codex logins are COPIED into the demo HOME
# on first run (originals untouched); gh works via GH_TOKEN from
# `gh auth token`.
set -eu
script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
demo_home=${PLAYGROUND_HOME:-/tmp/outfitter-playground-home}

cmd=${1:-claude}
case "$cmd" in
  reset) rm -rf "$demo_home"; echo "wiped $demo_home"; exit 0 ;;
  pi|claude|codex|check) ;;
  *) echo "usage: e2e/demo.sh [pi|claude|codex|check|reset]" >&2; exit 2 ;;
esac

# --- demo HOME: refresh credentials from the host on EVERY run -------------
# Host logins are the source of truth: OAuth tokens rotate, and a stale or
# emptied copy in the demo HOME (pi clears auth.json when a refresh fails)
# would otherwise stick around forever.
mkdir -p "$demo_home"
seed() { # seed <host-file> <demo-relative-path>
  [ -f "$1" ] || return 0
  mkdir -p "$demo_home/$(dirname "$2")"
  cp -f "$1" "$demo_home/$2"
}
seed "$HOME/.claude/.credentials.json" .claude/.credentials.json
# Claude Code keeps its account/onboarding state in ~/.claude.json — without
# it a fresh HOME asks to authenticate even with credentials present.
[ -f "$HOME/.claude.json" ] && [ ! -f "$demo_home/.claude.json" ] \
  && cp "$HOME/.claude.json" "$demo_home/.claude.json"
seed "$HOME/.codex/auth.json" .codex/auth.json
for f in auth.json settings.json models.json models-store.json; do
  seed "$HOME/.pi/agent/$f" ".pi/agent/$f"
done
# Fast mode for the claude legs (Opus-only; an unsupported default model
# auto-switches to Opus). Scoped to the demo HOME — your real ~/.claude
# settings are untouched. Costs more per token; delete the key to opt out.
node -e 'const fs=require("fs"),path=require("path"),p=process.argv[1];let s={};try{s=JSON.parse(fs.readFileSync(p,"utf8"))}catch{}s.fastMode=true;fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(s,null,2)+"\n")' \
  "$demo_home/.claude/settings.json"
if [ ! -f "$demo_home/.gitconfig" ]; then
  HOME="$demo_home" git config --global user.name  "$(git config user.name  || echo playground-demo)"
  HOME="$demo_home" git config --global user.email "$(git config user.email || echo demo@playground.invalid)"
fi

GH_TOKEN=$(gh auth token) || { echo "gh is not authenticated; run gh auth login" >&2; exit 1; }

run_demo() { # run a command in the demo environment
  env HOME="$demo_home" GH_TOKEN="$GH_TOKEN" \
    ${ANTHROPIC_API_KEY:+ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"} \
    ${OPENAI_API_KEY:+OPENAI_API_KEY="$OPENAI_API_KEY"} \
    "$@"
}

cd "$repo_root"

# --- free sanity check -----------------------------------------------------
if [ "$cmd" = check ]; then
  total=$(node bin/split.js 100 3 | awk '/^total/ {print $2}')
  [ "$total" = '$99.99' ] && echo "PASS  exhibit bug present (total $total)" \
    || { echo "FAIL  exhibit bug missing (total $total)"; exit 1; }
  npm test >/dev/null 2>&1 && echo "PASS  baseline suite green" \
    || { echo "FAIL  baseline suite red"; exit 1; }
  out=$(run_demo outfitter sync 2>&1) || { echo "FAIL  outfitter sync"; echo "$out" | tail -3; exit 1; }
  echo "$out" | grep -qE '⚠|✗' && { echo "FAIL  sync warnings:"; echo "$out" | grep -E '⚠|✗' | head -3; exit 1; }
  echo "PASS  outfitter sync clean"
  out=$(run_demo outfitter validate --strict 2>&1) \
    || { echo "FAIL  outfitter validate --strict"; echo "$out" | tail -5; exit 1; }
  echo "$out" | grep -qE '⚠|✗' && { echo "FAIL  validate warnings:"; echo "$out" | grep -E '⚠|✗' | head -3; exit 1; }
  echo "PASS  outfitter validate --strict clean"
  out=$(run_demo outfitter list 2>&1)
  for agent in engineer code-review git-forge-delegator; do
    echo "$out" | grep -qE "^\s+$agent\s+\[github:ai-outfitter/community-profiles#" \
      || { echo "FAIL  $agent not resolved from community-profiles"; exit 1; }
  done
  echo "PASS  engineer/code-review/git-forge-delegator resolve from community-profiles"
  exit 0
fi

# --- reset the checkout so every demo starts clean -------------------------
ref=origin/main
git remote get-url upstream >/dev/null 2>&1 && ref=upstream/main
echo "resetting checkout to $ref (uncommitted changes and extra branches are discarded)..."
git fetch -q "${ref%%/*}"
git checkout -qf main
git reset -q --hard "$ref"
git clean -qfd
git for-each-ref --format='%(refname:short)' refs/heads \
  | grep -v '^main$' | xargs -r git branch -qD

echo "syncing the community-profiles catalog..."
run_demo outfitter sync

cat <<EOF

┌─────────────────────────────────────────────────────────────────────┐
  playground demo — $repo_root  (HOME: $demo_home)

  The bug: node bin/split.js 100 3   totals \$99.99

  1. You are about to land in the ENGINEER agent ($cmd harness).
     Paste this prompt:

     Splitting \$100 among 3 people loses a cent — 'node bin/split.js
     100 3' totals \$99.99. File one scoped issue on this repository
     with acceptance criteria a reviewer can check mechanically (the
     report in docs/issues/0001-split-loses-cents.md is the template),
     then work that issue. Do not merge.

  2. Watch it: issue filed, fix/ branch, regression test, draft PR,
     CI green, PR marked ready.

  3. Exit the engineer session, then run the cold-context review:

     outfitter run code-review --harness $cmd

     Paste: Review the open pull request against its linked issue's
     acceptance criteria.

  4. Verify and merge yourself:

     node bin/split.js 100 3    # \$100.00
     npm test && gh pr merge --squash
└─────────────────────────────────────────────────────────────────────┘

EOF

# Outfitter's pi projection replaces pi's agent dir, which drops the user's
# defaultProvider/defaultModel — pi then falls back to an arbitrary model.
# Re-assert the demo HOME's pi defaults explicitly.
pi_args=()
if [ "$cmd" = pi ] && [ -f "$demo_home/.pi/agent/settings.json" ]; then
  defaults=$(node -e 's=require(process.argv[1]);if(s.defaultProvider)console.log(s.defaultProvider+" "+(s.defaultModel||""))' "$demo_home/.pi/agent/settings.json" 2>/dev/null || true)
  if [ -n "$defaults" ]; then
    # shellcheck disable=SC2086
    set -- $defaults
    pi_args=(--provider "$1"); [ -n "${2:-}" ] && pi_args+=(--model "$2")
    echo "pi model: ${1}${2:+/$2} (from your pi settings)"
  fi
fi

echo "launching the engineer session ($cmd) — paste the prompt above when it opens..."
run_demo outfitter run --harness "$cmd" ${pi_args[@]:+-- "${pi_args[@]}"} || true

cat <<EOF

Engineer session ended. This shell stays in the demo environment — next:
  outfitter run code-review --harness $cmd${pi_args:+ -- ${pi_args[@]}}
  gh pr view --web ; npm test ; gh pr merge --squash
(exit to leave; e2e/demo.sh to go again with a fresh slate)
EOF
exec env HOME="$demo_home" GH_TOKEN="$GH_TOKEN" \
  ${ANTHROPIC_API_KEY:+ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"} \
  ${OPENAI_API_KEY:+OPENAI_API_KEY="$OPENAI_API_KEY"} bash
