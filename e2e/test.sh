#!/usr/bin/env bash
# Demo cockpit: one command that preps everything and puts YOU in Outfitter,
# ready to demo the whole engineer flow live — issue filed by the agent, fix
# on a branch, draft PR, CI, cold-context adversarial review, merge-ready PR.
#
# What it wires before you land in the session:
#   * GH_TOKEN from `gh auth token`
#   * your fork of ai-outfitter/outfitter-playground — found by parentage,
#     created with `gh repo fork` if missing, force-RESET to upstream state,
#     open PRs closed, issues enabled
#   * your Claude Code / Codex logins mounted from ~/.claude and ~/.codex;
#     ANTHROPIC_API_KEY / OPENAI_API_KEY forwarded when set
#
# usage: e2e/test.sh [pi|claude|codex]   (default: claude)
#        e2e/test.sh check               free headless sanity check, no models
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

# Never force-reset anything that is not a playground fork.
parent=$(gh api "repos/$E2E_REPO" --jq '.parent.full_name // ""')
[ "$parent" = ai-outfitter/outfitter-playground ] \
  || { echo "$E2E_REPO is not a fork of ai-outfitter/outfitter-playground; refusing to reset it" >&2; exit 1; }

echo "resetting $E2E_REPO to the upstream state..."
tmp=$(mktemp -d)
git clone -q https://github.com/ai-outfitter/outfitter-playground.git "$tmp/up"
git -C "$tmp/up" push -q --force \
  "https://x-access-token:${GH_TOKEN}@github.com/$E2E_REPO.git" main:main
rm -rf "$tmp"
gh pr list -R "$E2E_REPO" --state open --json number --jq '.[].number' \
  | xargs -rn1 gh pr close -R "$E2E_REPO" --delete-branch >/dev/null 2>&1 || true
gh repo edit "$E2E_REPO" --enable-issues >/dev/null 2>&1 || true
echo "arena ready: https://github.com/$E2E_REPO"

args=(run --rm --entrypoint demo-entry
  -e GH_TOKEN="$GH_TOKEN" -e E2E_REPO="$E2E_REPO"
  -e GIT_AUTHOR_NAME="$(git config user.name || echo "$login")"
  -e GIT_AUTHOR_EMAIL="$(git config user.email || echo "$login@users.noreply.github.com")")
[ -t 0 ] && args+=(-it)   # interactive when run from a terminal
# Rootless podman remaps uids, making mounted credential files unreadable to
# the container user; keep-id preserves the caller's uid instead.
"$runner" version 2>/dev/null | grep -qi podman && args+=(--userns=keep-id)
[ -n "${ANTHROPIC_API_KEY:-}" ] && args+=(-e ANTHROPIC_API_KEY)
[ -n "${OPENAI_API_KEY:-}" ]    && args+=(-e OPENAI_API_KEY)
[ -n "${E2E_NO_LAUNCH:-}" ]     && args+=(-e E2E_NO_LAUNCH)
[ -f "$HOME/.claude/.credentials.json" ] \
  && args+=(-v "$HOME/.claude/.credentials.json:/creds/claude.json:ro")
[ -f "$HOME/.codex/auth.json" ] \
  && args+=(-v "$HOME/.codex/auth.json:/creds/codex.json:ro")

exec "$runner" "${args[@]}" playground-e2e "$harness"
