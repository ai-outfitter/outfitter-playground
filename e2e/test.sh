#!/usr/bin/env bash
# One command, whole workflow: run the full engineer flow — issue filed,
# engineer solves it, draft PR, CI, cold-context review, merge-ready PR —
# in a container, against YOUR FORK of ai-outfitter/outfitter-playground, using the
# credentials you already have:
#
#   * GH_TOKEN comes from `gh auth token`
#   * your fork is created with `gh repo fork` if it doesn't exist yet,
#     and force-reset to the upstream state before the run
#   * your Claude Code login (~/.claude/.credentials.json) and Codex login
#     (~/.codex/auth.json) are mounted in when present; ANTHROPIC_API_KEY /
#     OPENAI_API_KEY are forwarded when set
#
# usage: e2e/test.sh [pi|claude|codex|all|check]   (default: claude)
set -eu
cd "$(dirname "$0")"

harness=${1:-claude}
runner=$(command -v docker || command -v podman) || { echo "need docker or podman" >&2; exit 1; }

echo "building image..."
"$runner" build -q -t playground-e2e . >/dev/null

if [ "$harness" = check ]; then
  exec "$runner" run --rm playground-e2e check
fi

GH_TOKEN=$(gh auth token) || { echo "gh is not authenticated; run gh auth login" >&2; exit 1; }
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
echo "arena: $E2E_REPO (force-reset to upstream before each leg)"

args=(run --rm -e GH_TOKEN="$GH_TOKEN" -e E2E_REPO="$E2E_REPO")
[ -n "${ANTHROPIC_API_KEY:-}" ] && args+=(-e ANTHROPIC_API_KEY)
[ -n "${OPENAI_API_KEY:-}" ]    && args+=(-e OPENAI_API_KEY)
[ -n "${E2E_TIMEOUT:-}" ]       && args+=(-e E2E_TIMEOUT)
[ -n "${E2E_PI_ARGS:-}" ]       && args+=(-e E2E_PI_ARGS)
[ -f "$HOME/.claude/.credentials.json" ] \
  && args+=(-v "$HOME/.claude/.credentials.json:/creds/claude.json:ro")
[ -f "$HOME/.codex/auth.json" ] \
  && args+=(-v "$HOME/.codex/auth.json:/creds/codex.json:ro")

exec "$runner" "${args[@]}" playground-e2e "$harness" --forge
