#!/usr/bin/env bash
# Demo/test the software-factory flow: nothing runs on this host but `gh`.
# The agent runs in YOUR playground's GitHub Actions. This checkout's origin
# must be your own playground generated from the
# ai-outfitter/outfitter-playground template (issues and pull requests land
# there, never upstream), and its default branch must be software-factory,
# because issue events only reach the workflow on the default branch. The
# script makes that so, resets the arena to the upstream state, files the
# seeded bug with the trigger label, and watches the run.
#
# usage: e2e/factory.sh [run]      reset the arena, file + label the bug, watch (default)
#        e2e/factory.sh check      free sanity check: no model calls, nothing changed
#        e2e/factory.sh review     dispatch a re-review of the open factory PR
#        e2e/factory.sh status     show the open factory PR, its checks, and reviews
#
# env: OPENAI_API_KEY   set as the arena's secret when the arena has none
#      FACTORY_TOKEN    set as the arena's secret when the organization locks
#                       pull-request creation for the workflow token; when unset
#                       and locked, `gh auth token` is used with a notice
set -eu
script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
branch=software-factory
label=software-factory
workflow=software-factory.yml

cmd=${1:-run}
case "$cmd" in run|check|review|status) ;; *) echo "usage: e2e/factory.sh [run|check|review|status]" >&2; exit 2 ;; esac

cd "$repo_root"
GH_TOKEN=$(gh auth token) || { echo "gh is not authenticated; run gh auth login" >&2; exit 1; }
export GH_TOKEN

# --- free sanity check -----------------------------------------------------
if [ "$cmd" = check ]; then
  total=$(node bin/split.js 100 3 | awk '/^total/ {print $2}')
  [ "$total" = '$99.99' ] && echo "PASS  exhibit bug present (total $total)" \
    || { echo "FAIL  exhibit bug missing (total $total)"; exit 1; }
  npm test >/dev/null 2>&1 && echo "PASS  baseline suite green" || { echo "FAIL  baseline suite red"; exit 1; }
  [ -f ".github/workflows/$workflow" ] && echo "PASS  .github/workflows/$workflow present" \
    || { echo "FAIL  .github/workflows/$workflow missing — are you on the $branch branch?"; exit 1; }
  model=$(sed -n 's/^model:[[:space:]]*//p' .agents/agents/factory-engineer/agent.md | head -1)
  [ -n "$model" ] && echo "PASS  factory-engineer declares model $model" \
    || { echo "FAIL  factory-engineer declares no model"; exit 1; }
  out=$(outfitter sync 2>&1) || { echo "FAIL  outfitter sync"; echo "$out" | tail -3; exit 1; }
  out=$(outfitter validate --strict 2>&1) || { echo "FAIL  outfitter validate --strict"; echo "$out" | tail -5; exit 1; }
  echo "PASS  outfitter validate --strict clean"
  outfitter list agents 2>&1 | grep -qE '^\s+factory-engineer\s' && echo "PASS  factory-engineer resolves over the community catalog" \
    || { echo "FAIL  factory-engineer not resolved"; exit 1; }
  exit 0
fi

# --- demo arena: this checkout, generated from the template ----------------
case "$(git remote get-url origin)" in
  *ai-outfitter/outfitter-playground*)
    echo "origin is the upstream org repo. Generate your own playground and point origin at it:" >&2
    echo "  gh repo create <you>/outfitter-playground --template ai-outfitter/outfitter-playground --public --include-all-branches" >&2
    echo "  git remote set-url origin git@github.com:<you>/outfitter-playground.git" >&2
    exit 1 ;;
esac
arena=$(git remote get-url origin | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')
lineage=$(gh api "repos/$arena" --jq '.template_repository.full_name // ""' 2>/dev/null)
if [ "$lineage" != ai-outfitter/outfitter-playground ]; then
  echo "$arena was not generated from ai-outfitter/outfitter-playground; refusing to touch it." >&2
  exit 1
fi
git remote get-url upstream >/dev/null 2>&1 \
  || git remote add upstream https://github.com/ai-outfitter/outfitter-playground.git
gh repo set-default "$arena" >/dev/null 2>&1 || true

factory_pr() { # the open pull request the factory opened for the seeded issue
  gh pr list -R "$arena" --state open --json number,body,headRefName \
    --jq '[.[] | select(.body | test("(?i)(close[sd]?|fix(e[sd])?|resolve[sd]?) #[0-9]+"))] | first | .number // empty'
}

show_status() {
  local n; n=$(factory_pr)
  [ -n "$n" ] || { echo "no open factory pull request on $arena"; return 0; }
  echo "pull request: https://github.com/$arena/pull/$n"
  gh pr view "$n" -R "$arena" --json isDraft,headRefName,body --jq '"  branch \(.headRefName)  draft=\(.isDraft)\n  \(.body | split("\n") | last)"'
  gh pr checks "$n" -R "$arena" 2>/dev/null | sed 's/^/  check: /' || true
  gh api "repos/$arena/pulls/$n/reviews" --jq '.[] | "  review by \(.user.login) [\(.state)]: \(.body | split("\n") | first)"'
}

if [ "$cmd" = status ]; then show_status; exit 0; fi

if [ "$cmd" = review ]; then
  n=$(factory_pr); [ -n "$n" ] || { echo "no open factory pull request to review" >&2; exit 1; }
  issue=$(gh pr view "$n" -R "$arena" --json body --jq '.body | capture("(?i)(close[sd]?|fix(e[sd])?|resolve[sd]?) #(?<n>[0-9]+)").n')
  gh workflow run "$workflow" -R "$arena" --ref "$branch" -f issue="$issue" -f pr="$n" -f step=review
  echo "dispatched a re-review of #$n; gh run watch -R $arena"
  exit 0
fi

# --- run: make the arena ready, reset it, file the bug, watch ---------------
echo "preflight on $arena..."
if [ "$(gh repo view "$arena" --json defaultBranchRef --jq .defaultBranchRef.name)" != "$branch" ]; then
  git fetch -q upstream
  git push -q origin "refs/remotes/upstream/$branch:refs/heads/$branch" 2>/dev/null || true
  gh repo edit "$arena" --default-branch "$branch" >/dev/null
  echo "  default branch set to $branch (issue events only reach the default branch)"
fi
secrets=$(gh secret list -R "$arena" --json name --jq '.[].name' 2>/dev/null || true)
if ! grep -qx OPENAI_API_KEY <<<"$secrets"; then
  [ -n "${OPENAI_API_KEY:-}" ] || { echo "the arena has no OPENAI_API_KEY secret and none is in the environment; export one or gh secret set OPENAI_API_KEY -R $arena" >&2; exit 1; }
  printf '%s' "$OPENAI_API_KEY" | gh secret set OPENAI_API_KEY -R "$arena"
  echo "  OPENAI_API_KEY secret set from the environment"
fi
if ! grep -qx FACTORY_TOKEN <<<"$secrets"; then
  if ! gh api "repos/$arena/actions/permissions/workflow" --jq .can_approve_pull_request_reviews | grep -qx true; then
    if gh api -X PUT "repos/$arena/actions/permissions/workflow" -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true >/dev/null 2>&1; then
      echo "  enabled: Allow GitHub Actions to create and approve pull requests"
    else
      token=${FACTORY_TOKEN:-$GH_TOKEN}
      printf '%s' "$token" | gh secret set FACTORY_TOKEN -R "$arena"
      [ -n "${FACTORY_TOKEN:-}" ] && echo "  FACTORY_TOKEN secret set from the environment" \
        || echo "  the organization locks pull-request creation for the workflow token: FACTORY_TOKEN set from gh auth token (your token; gh secret delete FACTORY_TOKEN -R $arena to remove)"
    fi
  fi
fi
gh label list -R "$arena" --json name --jq '.[].name' | grep -qx "$label" \
  || gh label create "$label" -R "$arena" --color 0e8a16 --description "Route this issue to the software factory" >/dev/null

echo "resetting the arena to the upstream $branch (open PRs, issues, and extra branches are discarded)..."
git fetch -q upstream
git checkout -qf "$branch" 2>/dev/null || git checkout -qb "$branch" "upstream/$branch"
git reset -q --hard "upstream/$branch"
git clean -qfd
git for-each-ref --format='%(refname:short)' refs/heads | grep -vx "$branch" | xargs -r git branch -qD
git push -q --force origin "$branch"
gh pr list -R "$arena" --state open --json number --jq '.[].number' \
  | xargs -rn1 gh pr close -R "$arena" --delete-branch >/dev/null 2>&1 || true
gh issue list -R "$arena" --state open --json number --jq '.[].number' \
  | xargs -rn1 gh issue close -R "$arena" >/dev/null 2>&1 || true

echo "filing the seeded bug and labelling it $label..."
url=$(gh issue create -R "$arena" --title "split loses cents on uneven amounts" --body-file docs/issues/0001-split-loses-cents.md)
issue=${url##*/}
gh issue edit "$issue" -R "$arena" --add-label "$label" >/dev/null
echo "  $url"

echo "waiting for the factory run to start..."
run_id=""
for _ in $(seq 1 30); do
  run_id=$(gh run list -R "$arena" --workflow "$workflow" --limit 1 --json databaseId,createdAt --jq '.[0].databaseId // empty')
  [ -n "$run_id" ] && break
  sleep 5
done
[ -n "$run_id" ] || { echo "no run started; is $workflow on the default branch and Actions enabled?" >&2; exit 1; }
echo "  https://github.com/$arena/actions/runs/$run_id"
gh run watch "$run_id" -R "$arena" --exit-status || echo "the run did not succeed; the log is at the URL above"

echo
show_status
cat <<STATUS

Verify and merge yourself:
  gh pr checkout <n> && node bin/split.js 100 3 && npm test && gh pr merge --squash
Re-review: e2e/factory.sh review    Status: e2e/factory.sh status
STATUS
