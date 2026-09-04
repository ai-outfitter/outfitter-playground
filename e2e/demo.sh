#!/usr/bin/env bash
# Demo/test the engineer flow on your host — no container. Runs Outfitter
# under a persistent, isolated HOME in /tmp so harness state (logins,
# onboarding, the synced catalog) survives between runs without touching
# your real ~. It runs in this checkout, whose origin must be YOUR OWN
# playground generated from the ai-outfitter/outfitter-playground template,
# so issues and pull requests land there, never upstream. The checkout is
# reset to the upstream state each run so the seeded bug is back.
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

# --- demo arena: this checkout, generated from the template ----------------
# Issues and PRs land wherever origin points. The arena is a repo GENERATED
# from ai-outfitter/outfitter-playground ("Use this template"), not a fork:
# generated repos run Actions immediately and have issues enabled, where
# forks need one-time UI clicks for both. Refuse the org repo itself.
case "$(git remote get-url origin)" in
  *ai-outfitter/outfitter-playground*)
    echo "origin is the upstream org repo. Generate your own playground and point origin at it:" >&2
    echo "  gh repo create <you>/outfitter-playground --template ai-outfitter/outfitter-playground --public" >&2
    echo "  git remote set-url origin git@github.com:<you>/outfitter-playground.git" >&2
    exit 1 ;;
esac
# Derive the arena from origin — with two github remotes, gh's own
# resolution prefers upstream, which is exactly the wrong target here.
arena=$(git remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')
lineage=$(gh api "repos/$arena" --jq '.template_repository.full_name // ""' 2>/dev/null)
if [ "$lineage" != ai-outfitter/outfitter-playground ]; then
  echo "$arena was not generated from ai-outfitter/outfitter-playground; refusing to reset it." >&2
  echo "  gh repo create <you>/outfitter-playground --template ai-outfitter/outfitter-playground --public" >&2
  exit 1
fi
git remote get-url upstream >/dev/null 2>&1 \
  || git remote add upstream https://github.com/ai-outfitter/outfitter-playground.git
# Bare gh commands in the demo session (the agent's `gh issue create`,
# `gh pr create`) must target the arena, not upstream.
gh repo set-default "$arena" >/dev/null 2>&1 || true

echo "resetting checkout to the upstream state (uncommitted changes and extra branches are discarded)..."
git fetch -q upstream
git checkout -qf main
git reset -q --hard upstream/main
git clean -qfd
# Agents follow the worktree convention, so demo branches may live in
# sibling worktrees; remove those before deleting the branches.
git worktree list --porcelain | awk '/^worktree /{print $2}' | tail -n +2 \
  | xargs -rn1 git worktree remove --force
git worktree prune
git for-each-ref --format='%(refname:short)' refs/heads \
  | grep -v '^main$' | xargs -r git branch -qD
git push -q --force origin main
gh pr list -R "$arena" --state open --json number --jq '.[].number' \
  | xargs -rn1 gh pr close -R "$arena" --delete-branch >/dev/null 2>&1 || true

echo "syncing the community-profiles catalog..."
run_demo outfitter sync

cat <<EOF

┌─────────────────────────────────────────────────────────────────────┐
  playground demo — $repo_root
  arena: $arena   (HOME: $demo_home)

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
