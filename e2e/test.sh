#!/usr/bin/env bash
# Automatic end-to-end test: runs the whole engineer flow headlessly with
# YOUR credentials wired in — no env setup, no interaction. The agent files
# the issue on your fork, fixes the seeded bug, opens a draft PR, waits for
# CI, marks it ready, and a cold-context reviewer submits a formal review.
# Your fork is force-reset to the upstream state first, so runs repeat.
#
# Wires automatically: GH_TOKEN from `gh auth token`; your fork (found by
# parentage, created if missing); your Claude Code / Codex logins from
# ~/.claude and ~/.codex; ANTHROPIC_API_KEY / OPENAI_API_KEY when set.
#
# usage: e2e/test.sh [pi|claude|codex|all] [--local]   (default: claude)
#        e2e/test.sh check          free sanity check, no credentials needed
#   --local  skip the forge: implement + review in-container only
#
# Want to drive it yourself instead? e2e/demo.sh drops you into the session.
set -eu
cd "$(dirname "$0")"

harness=claude
mode=--forge
for arg in "$@"; do
  case "$arg" in
    pi|claude|codex|all|check) harness=$arg ;;
    --local) mode= ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

runner=$(command -v docker || command -v podman) || { echo "need docker or podman" >&2; exit 1; }
echo "building image..."
"$runner" build -q -t playground-e2e . >/dev/null

args=(run --rm)
"$runner" version 2>/dev/null | grep -qi podman && args+=(--userns=keep-id)

if [ "$harness" != check ]; then
  GH_TOKEN=$(gh auth token) || { echo "gh is not authenticated; run gh auth login" >&2; exit 1; }
  args+=(-e GH_TOKEN="$GH_TOKEN")
  if [ -n "$mode" ]; then
    login=$(gh api user --jq .login)
    find_fork() {
      gh api repos/ai-outfitter/outfitter-playground/forks --paginate \
        --jq ".[] | select(.owner.login == \"$login\") | .full_name" | head -1
    }
    if [ -z "${E2E_REPO:-}" ]; then
      E2E_REPO=$(find_fork)
      if [ -z "$E2E_REPO" ]; then
        echo "forking ai-outfitter/outfitter-playground..."
        gh repo fork ai-outfitter/outfitter-playground --clone=false
        sleep 5
        E2E_REPO=$(find_fork)
      fi
      [ -n "$E2E_REPO" ] || { echo "could not find or create your fork" >&2; exit 1; }
    fi
    echo "arena: $E2E_REPO (force-reset to upstream inside the run)"
    args+=(-e E2E_REPO="$E2E_REPO")
  fi
  [ -n "${ANTHROPIC_API_KEY:-}" ] && args+=(-e ANTHROPIC_API_KEY)
  [ -n "${OPENAI_API_KEY:-}" ]    && args+=(-e OPENAI_API_KEY)
  [ -n "${E2E_TIMEOUT:-}" ]       && args+=(-e E2E_TIMEOUT)
  [ -n "${E2E_PI_ARGS:-}" ]       && args+=(-e E2E_PI_ARGS)
  [ -f "$HOME/.claude/.credentials.json" ] \
    && args+=(-v "$HOME/.claude/.credentials.json:/creds/claude.json:ro")
  [ -f "$HOME/.codex/auth.json" ] \
    && args+=(-v "$HOME/.codex/auth.json:/creds/codex.json:ro")
fi

# shellcheck disable=SC2086
exec "$runner" "${args[@]}" playground-e2e "$harness" $mode
