#!/usr/bin/env bash
# Container-side bootstrap for the demo: copy in your credentials, use the
# mounted repo (or clone the fork named in E2E_REPO when nothing is
# mounted), sync the catalog, print the demo script, then hand you an
# interactive Outfitter session running the engineer. When you exit that
# session you land in a shell in the repo, ready for review and merge.
set -eu
harness=${1:-claude}

for cred in claude:.claude/.credentials.json codex:.codex/auth.json; do
  src=/creds/${cred%%:*}.json dst=$HOME/${cred#*:}
  [ -e "$src" ] || continue
  [ -r "$src" ] || { echo "FATAL: $src mounted but unreadable (rootless podman needs --userns=keep-id; the wrapper scripts pass it)" >&2; exit 1; }
  mkdir -p "$(dirname "$dst")" && cp "$src" "$dst"
done

[ -n "${GIT_AUTHOR_NAME:-}" ]  && git config --global user.name  "$GIT_AUTHOR_NAME"
[ -n "${GIT_AUTHOR_EMAIL:-}" ] && git config --global user.email "$GIT_AUTHOR_EMAIL"

if [ -d /workspace/playground/.git ]; then
  cd /workspace/playground
  where="your mounted checkout"
else
  : "${E2E_REPO:?no repo mounted and E2E_REPO unset}" "${GH_TOKEN:?}"
  echo "cloning $E2E_REPO..."
  git clone -q "https://x-access-token:${GH_TOKEN}@github.com/${E2E_REPO}.git" /workspace/playground
  cd /workspace/playground
  where="a fresh clone of $E2E_REPO"
fi

# The container has no SSH keys; route git pushes over token HTTPS whatever
# scheme the origin remote uses. Global config lives in the container's HOME,
# so the mounted repo's own config is untouched.
if [ -n "${GH_TOKEN:-}" ]; then
  git config --global url."https://x-access-token:${GH_TOKEN}@github.com/".insteadOf "git@github.com:"
  git config --global --add url."https://x-access-token:${GH_TOKEN}@github.com/".insteadOf "https://github.com/"
fi

echo "syncing the community-profiles catalog..."
outfitter sync

cat <<EOF

┌─────────────────────────────────────────────────────────────────────┐
  playground demo — $where

  The bug: node bin/split.js 100 3   totals \$99.99

  1. You are about to land in the ENGINEER agent ($harness harness).
     Paste this prompt:

     Splitting \$100 among 3 people loses a cent — 'node bin/split.js
     100 3' totals \$99.99. File one scoped issue on this repository
     with acceptance criteria a reviewer can check mechanically (the
     report in docs/issues/0001-split-loses-cents.md is the template),
     then work that issue. Do not merge.

  2. Watch it: issue filed, fix/ branch, regression test, draft PR,
     CI green, PR marked ready.

  3. Exit the engineer session, then run the cold-context review:

     outfitter run code-review --harness $harness

     Paste: Review the open pull request against its linked issue's
     acceptance criteria.

  4. Verify and merge yourself:

     node bin/split.js 100 3    # \$100.00
     npm test && gh pr merge --squash
└─────────────────────────────────────────────────────────────────────┘

EOF

if [ -n "${E2E_NO_LAUNCH:-}" ]; then
  echo "(E2E_NO_LAUNCH set — bootstrap verified, not launching)"
  exit 0
fi

echo "launching the engineer session ($harness) — paste the prompt above when it opens..."
outfitter run --harness "$harness" || true

cat <<EOF

Engineer session ended. You are in the repo — next steps:
  outfitter run code-review --harness $harness
  gh pr view --web ; npm test ; gh pr merge --squash
EOF
exec bash
