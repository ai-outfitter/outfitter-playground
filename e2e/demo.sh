#!/usr/bin/env bash
# Demo/test the engineer flow on your host — no container. Runs Outfitter
# under a persistent, isolated HOME in /tmp so harness state (logins,
# onboarding, the synced catalog) survives between runs without touching
# your real ~. The session works in a persistent clone of YOUR FORK inside
# that HOME — issues and pull requests land on the fork, never upstream,
# and your own checkout is never touched. The fork clone is reset to the
# upstream state each run so the seeded bug is back.
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
# Fast mode is only available on codex right now: seed the codex config and
# set service_tier = "priority" in the DEMO copy only — your real
# ~/.codex/config.toml keeps its own tier.
seed "$HOME/.codex/config.toml" .codex/config.toml
if [ -f "$demo_home/.codex/config.toml" ]; then
  if grep -q '^service_tier' "$demo_home/.codex/config.toml"; then
    sed -i 's/^service_tier *=.*/service_tier = "priority"/' "$demo_home/.codex/config.toml"
  else
    printf 'service_tier = "priority"\n' >> "$demo_home/.codex/config.toml"
  fi
fi
if [ ! -f "$demo_home/.gitconfig" ]; then
  HOME="$demo_home" git config --global user.name  "$(git config user.name  || echo playground-demo)"
  HOME="$demo_home" git config --global user.email "$(git config user.email || echo demo@playground.invalid)"
  # git speaks to github over https through gh, so no token ever hits disk
  HOME="$demo_home" git config --global credential."https://github.com".helper '!gh auth git-credential'
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
  out=$(run_demo outfitter validate --strict 2>&1) && validate_rc=0 || validate_rc=$?
  # A settings.local.yml catalog override is deliberate, visible divergence;
  # its replaced-source warning is the only one a local-dev checkout may show.
  real_warnings=$(echo "$out" | grep -E '⚠|✗' | grep -vE "replaced by .*settings.local.yml|Validation failed" || true)
  if [ -n "$real_warnings" ]; then
    echo "FAIL  validate warnings:"; echo "$real_warnings" | head -3; exit 1
  fi
  if [ "$validate_rc" -ne 0 ] && [ ! -f .agents/settings.local.yml ]; then
    echo "FAIL  outfitter validate --strict"; echo "$out" | tail -5; exit 1
  fi
  if [ -f .agents/settings.local.yml ]; then
    echo "PASS  outfitter validate clean (local catalog override active)"
  else
    echo "PASS  outfitter validate --strict clean"
  fi
  out=$(run_demo outfitter list 2>&1)
  for agent in engineer code-review git-forge-delegator; do
    echo "$out" | grep -qE "^\s+$agent\s+\[(github:ai-outfitter/community-profiles#|/.*community-profiles)" \
      || { echo "FAIL  $agent not resolved from community-profiles"; exit 1; }
  done
  echo "PASS  engineer/code-review/git-forge-delegator resolve from community-profiles"
  exit 0
fi

# --- demo workspace: a persistent clone of YOUR FORK -----------------------
# The session must never write to upstream: origin in the workspace is your
# fork, upstream is the org repo, and the workspace is reset to the upstream
# state each run.
login=$(gh api user --jq .login)
fork=$(gh api repos/ai-outfitter/outfitter-playground/forks --paginate \
  --jq ".[] | select(.owner.login == \"$login\") | .full_name" | head -1)
if [ -z "$fork" ]; then
  echo "forking ai-outfitter/outfitter-playground..."
  gh repo fork ai-outfitter/outfitter-playground --clone=false >/dev/null
  sleep 5
  fork=$(gh api repos/ai-outfitter/outfitter-playground/forks --paginate \
    --jq ".[] | select(.owner.login == \"$login\") | .full_name" | head -1)
fi
[ -n "$fork" ] || { echo "could not find or create your fork" >&2; exit 1; }
gh repo edit "$fork" --enable-issues >/dev/null 2>&1 || true

workspace=$demo_home/playground
if [ ! -d "$workspace/.git" ]; then
  echo "cloning $fork into the demo HOME..."
  run_demo git clone -q "https://github.com/$fork.git" "$workspace"
  run_demo git -C "$workspace" remote add upstream https://github.com/ai-outfitter/outfitter-playground.git
fi
echo "resetting $fork clone to the upstream state..."
run_demo git -C "$workspace" fetch -q upstream
run_demo git -C "$workspace" checkout -qf main
run_demo git -C "$workspace" reset -q --hard upstream/main
run_demo git -C "$workspace" clean -qfd
run_demo git -C "$workspace" for-each-ref --format='%(refname:short)' refs/heads \
  | grep -v '^main$' | xargs -r env HOME="$demo_home" git -C "$workspace" branch -qD
run_demo git -C "$workspace" push -q --force origin main
gh pr list -R "$fork" --state open --json number --jq '.[].number' \
  | xargs -rn1 gh pr close -R "$fork" --delete-branch >/dev/null 2>&1 || true

# Carry a local catalog override into the workspace (gitignored there too).
[ -f "$repo_root/.agents/settings.local.yml" ] \
  && cp "$repo_root/.agents/settings.local.yml" "$workspace/.agents/settings.local.yml"

cd "$workspace"
echo "syncing the community-profiles catalog..."
run_demo outfitter sync

cat <<EOF

┌─────────────────────────────────────────────────────────────────────┐
  playground demo — $workspace
  fork: $fork   (HOME: $demo_home; your own checkout is untouched)

  The bug: node bin/split.js 100 3   totals \$99.99

  1. You are about to land in the ENGINEER agent ($cmd harness).
     Paste this bug report — nothing more:

     Splitting \$100 among 3 people loses a cent — 'node bin/split.js
     100 3' totals \$99.99. The shares should always sum to the
     amount. Do not merge.

  2. Watch the SDLC come from the loadout, not the prompt: the
     engineer's scoped-issues skill reproduces the report and files the
     scoped issue itself, then fix/ branch, regression test, draft PR,
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

if [ -n "${E2E_NO_LAUNCH:-}" ]; then
  echo "(E2E_NO_LAUNCH set — bootstrap verified, not launching)"
  exit 0
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
