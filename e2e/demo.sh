#!/usr/bin/env bash
# Demo cockpit: mounts THIS repo checkout into the container and puts you in
# an interactive Outfitter session, ready to demo the engineer flow live.
# No cloning — the agent works your actual working tree, and branches/PRs it
# makes are really yours. Each run RESETS the checkout first: hard-reset main
# to upstream (or origin), delete other local branches, drop untracked files
# — so the seeded bug is back and the demo starts clean. Wired automatically:
#
#   * GH_TOKEN from `gh auth token` (gh + git pushes work in the container,
#     even though your origin remote is SSH)
#   * your Claude Code / Codex logins mounted from ~/.claude and ~/.codex;
#     ANTHROPIC_API_KEY / OPENAI_API_KEY forwarded when set
#   * your git name/email for the commits the agent makes
#
# Reset when you want a clean slate: see README "Reset and go again", or run
# the automatic e2e (e2e/test.sh) which force-resets your fork.
#
# usage: e2e/demo.sh [pi|claude|codex]   (default: claude)
set -eu
cd "$(dirname "$0")"
repo_root=$(git rev-parse --show-toplevel)

harness=${1:-claude}
runner=$(command -v docker || command -v podman) || { echo "need docker or podman" >&2; exit 1; }

echo "building image..."
"$runner" build -q -t playground-e2e . >/dev/null

GH_TOKEN=$(gh auth token) || { echo "gh is not authenticated; run gh auth login" >&2; exit 1; }

ref=origin/main
git -C "$repo_root" remote get-url upstream >/dev/null 2>&1 && ref=upstream/main
echo "resetting checkout to $ref (uncommitted changes and extra branches are discarded)..."
git -C "$repo_root" fetch -q "${ref%%/*}"
git -C "$repo_root" checkout -qf main
git -C "$repo_root" reset -q --hard "$ref"
git -C "$repo_root" clean -qfd
git -C "$repo_root" for-each-ref --format='%(refname:short)' refs/heads \
  | grep -v '^main$' | xargs -r git -C "$repo_root" branch -qD

args=(run --rm --entrypoint demo-entry
  -e GH_TOKEN="$GH_TOKEN"
  -e GIT_AUTHOR_NAME="$(git config user.name || true)"
  -e GIT_AUTHOR_EMAIL="$(git config user.email || true)"
  -v "$repo_root:/workspace/playground")
[ -t 0 ] && args+=(-it)   # interactive when run from a terminal
# Rootless podman remaps uids, making mounted files unreadable to the
# container user; keep-id preserves the caller's uid instead.
"$runner" version 2>/dev/null | grep -qi podman && args+=(--userns=keep-id)
[ -n "${ANTHROPIC_API_KEY:-}" ] && args+=(-e ANTHROPIC_API_KEY)
[ -n "${OPENAI_API_KEY:-}" ]    && args+=(-e OPENAI_API_KEY)
[ -n "${E2E_NO_LAUNCH:-}" ]     && args+=(-e E2E_NO_LAUNCH)
[ -f "$HOME/.claude/.credentials.json" ] \
  && args+=(-v "$HOME/.claude/.credentials.json:/creds/claude.json:ro")
[ -f "$HOME/.codex/auth.json" ] \
  && args+=(-v "$HOME/.codex/auth.json:/creds/codex.json:ro")

echo "starting container with $repo_root mounted — catalog sync takes a few seconds, then the engineer session opens..."
exec "$runner" "${args[@]}" playground-e2e "$harness"
