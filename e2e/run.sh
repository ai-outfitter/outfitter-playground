#!/usr/bin/env bash
# playground-e2e — prove the engineer flow works, per harness, from a clean
# slate every time. "Works" means what a new user would experience:
#
#   * outfitter sync / validate --strict / list run clean — zero warnings
#   * the composed agents resolve from the community-profiles catalog
#   * the engineer agent fixes the seeded bug, adds the regression test,
#     verifies, and commits on a semantic branch
#   * a cold-context code-review agent delivers a verdict
#   * (forge mode) the whole thing lands as issue -> draft PR -> CI ->
#     formal review -> a PR ready for a human to merge
#
# usage: playground-e2e [pi|claude|codex|all|check] [--forge]
#
#   check          no-model smoke: tools present, clone, baseline, sync,
#                  validate, catalog attribution. Free — run this first.
#   pi|claude|...  one harness leg, local mode (no forge writes)
#   all            every harness with a credential present
#   --forge        full forge flow against $E2E_REPO (a scratch fork you own;
#                  requires GH_TOKEN). The scratch repo is force-reset first.
#
# env: ANTHROPIC_API_KEY / OPENAI_API_KEY  harness credentials (a leg is
#        skipped when its credential is absent)
#      E2E_SRC        repo to test (default upstream URL; mount your checkout
#                     at /src to test local changes)
#      E2E_REPO       owner/repo scratch fork for --forge
#      E2E_TIMEOUT    seconds per agent run (default 900)
#      E2E_PI_ARGS    pi provider/model override, e.g. "--provider openai --model *gpt*"
set -u

E2E_SRC=${E2E_SRC:-https://github.com/ai-outfitter/outfitter-playground.git}
[ -d /src/.git ] && E2E_SRC=/src
E2E_TIMEOUT=${E2E_TIMEOUT:-900}
ISSUE_DOC=docs/issues/0001-split-loses-cents.md

MODE=local
TARGET=all
for arg in "$@"; do
  case "$arg" in
    --forge) MODE=forge ;;
    pi|claude|codex|all|check) TARGET=$arg ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

PASS=() ; FAIL=() ; SKIP=()
note() { printf '\n=== %s\n' "$*"; }
ok()   { PASS+=("$1"); printf 'PASS  %s\n' "$1"; }
bad()  { FAIL+=("$1: $2"); printf 'FAIL  %s — %s\n' "$1" "$2"; }
skip() { SKIP+=("$1: $2"); printf 'SKIP  %s — %s\n' "$1" "$2"; }

in_container() { [ -f /.dockerenv ] || [ -n "${container:-}" ] || [ "${E2E_ALLOW_UNSANDBOXED:-}" = 1 ]; }

total_for() { ( cd "$1" && node bin/split.js 100 3 | awk '/^total/ {print $2}' ); }

# Warnings are demo failures: a new user should never see ⚠ or ✗ from the
# repo's own payload. $1 = leg name, $2 = captured output.
warn_scan() {
  local hits
  hits=$(grep -anE '⚠|✗|WARN|warning' "$2" | grep -vi 'deprecat' | head -5)
  [ -z "$hits" ] && return 0
  bad "$1" "warnings in output: $hits"
  return 1
}

fresh_clone() { # stdout: the new workdir. The fresh clone IS the reset.
  local work; work=$(mktemp -d)
  git clone -q "$E2E_SRC" "$work/playground" || return 1
  echo "$work/playground"
}

git config --global user.name  >/dev/null 2>&1 || git config --global user.name  playground-e2e
git config --global user.email >/dev/null 2>&1 || git config --global user.email e2e@playground.invalid

# Harness logins mounted by e2e/test.sh land read-only in /creds; copy them
# into this container's HOME where the CLIs expect them.
[ -f /creds/claude.json ] && { mkdir -p "$HOME/.claude"; cp /creds/claude.json "$HOME/.claude/.credentials.json"; }
[ -f /creds/codex.json ]  && { mkdir -p "$HOME/.codex";  cp /creds/codex.json  "$HOME/.codex/auth.json"; }

# --- static leg: everything a new user sees before any model call ----------
static_checks() {
  local repo=$1 out=/tmp/e2e-static.log
  ( cd "$repo" &&
    { total=$(total_for .); [ "$total" = '$99.99' ] || { echo "exhibit bug missing (total=$total)"; exit 1; }; } &&
    npm test >/dev/null 2>&1 || { echo "baseline suite red"; exit 1; }
  ) > "$out" 2>&1 || { bad static "$(cat "$out")"; return 1; }
  ok "static: exhibit intact, baseline suite green"

  ( cd "$repo" && outfitter sync ) > "$out" 2>&1 \
    || { bad "static: outfitter sync" "$(tail -3 "$out")"; return 1; }
  warn_scan "static: sync warning-free" "$out" || return 1
  ok "static: outfitter sync clean"

  ( cd "$repo" && outfitter validate --strict ) > "$out" 2>&1 \
    || { bad "static: outfitter validate --strict" "$(tail -5 "$out")"; return 1; }
  warn_scan "static: validate warning-free" "$out" || return 1
  ok "static: outfitter validate --strict clean"

  ( cd "$repo" && outfitter list ) > "$out" 2>&1
  local missing=
  for agent in engineer code-review git-forge-delegator; do
    grep -E "^\s+$agent\s+\[github:ai-outfitter/community-profiles#" "$out" >/dev/null || missing="$missing $agent"
  done
  if [ -n "$missing" ]; then
    bad "static: community-profiles attribution" "not resolved from the catalog:$missing"
    return 1
  fi
  ok "static: engineer/code-review/git-forge-delegator resolve from community-profiles"
}

# --- one agent run, headless, per harness ----------------------------------
launch() { # $1 harness, $2 agent, $3 prompt, $4 logfile
  local harness=$1 agent=$2 prompt=$3 log=$4
  case "$harness" in
    pi)
      local pi_args=${E2E_PI_ARGS:-}
      if [ -z "$pi_args" ]; then
        if [ -n "${ANTHROPIC_API_KEY:-}" ]; then pi_args='--provider anthropic --model *sonnet*'
        else pi_args='--provider openai --model *gpt*'; fi
      fi
      # shellcheck disable=SC2086
      timeout "$E2E_TIMEOUT" outfitter run "$agent" --strict -- -p $pi_args "$prompt" ;;
    claude)
      in_container || { echo "refusing --dangerously-skip-permissions outside a container (set E2E_ALLOW_UNSANDBOXED=1 to override)"; return 3; }
      timeout "$E2E_TIMEOUT" outfitter run "$agent" --strict --harness claude -- -p --dangerously-skip-permissions "$prompt" ;;
    codex)
      in_container || { echo "refusing sandbox bypass outside a container (set E2E_ALLOW_UNSANDBOXED=1 to override)"; return 3; }
      # No --strict: codex cannot project the composed identity yet and strict
      # would abort. The identity-drop warning is expected and reported below.
      timeout "$E2E_TIMEOUT" outfitter run "$agent" --harness codex -- exec --dangerously-bypass-approvals-and-sandbox "$prompt" ;;
  esac > "$log" 2>&1
}

cred_for() {
  case "$1" in
    claude) [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -f "$HOME/.claude/.credentials.json" ] ;;
    codex)  [ -n "${OPENAI_API_KEY:-}" ] || [ -f "$HOME/.codex/auth.json" ] ;;
    pi)     [ -n "${ANTHROPIC_API_KEY:-}${OPENAI_API_KEY:-}${E2E_PI_ARGS:-}" ] ;;
  esac
}

# --- local mode: implement + review with no forge writes -------------------
local_leg() {
  local harness=$1 log=/tmp/e2e-$harness.log repo
  note "local leg: $harness"
  cred_for "$harness" || { skip "$harness" "no credential in env"; return 0; }
  repo=$(fresh_clone) || { bad "$harness: clone" "cannot clone $E2E_SRC"; return 1; }
  ( cd "$repo" && outfitter sync >/dev/null 2>&1 )

  local prompt="Read AGENTS.md, then work the bug report in $ISSUE_DOC as a LOCAL-ONLY exercise: create a fix/ branch, implement the fix in src/split.js, add the regression test the acceptance criteria demand, verify with npm test, and commit with a conventional commit message. Do not push, do not open a pull request, do not use gh or the network. End by naming the branch."
  ( cd "$repo" && launch "$harness" engineer "$prompt" "$log" )
  local rc=$?
  [ $rc -eq 3 ] && { skip "$harness" "$(cat "$log")"; return 0; }
  [ $rc -ne 0 ] && { bad "$harness: engineer run" "exit $rc — tail: $(tail -3 "$log")"; return 1; }

  local branch
  branch=$(cd "$repo" && git for-each-ref --format='%(refname:short)' refs/heads | grep -v '^main$' | head -1)
  [ -n "$branch" ] || { bad "$harness: branch" "no non-main branch created"; return 1; }
  echo "$branch" | grep -qE '^(fix|feat)/' || bad "$harness: branch" "'$branch' is not semantic"
  ( cd "$repo" && git checkout -q "$branch" )
  [ -z "$(cd "$repo" && git status --porcelain)" ] || { bad "$harness: commit" "uncommitted changes left behind"; return 1; }
  ( cd "$repo" && git diff --name-only main.."$branch" | grep -q '^test/split.test.js$' ) \
    || { bad "$harness: regression test" "test/split.test.js unchanged"; return 1; }
  ( cd "$repo" && npm test >/dev/null 2>&1 ) || { bad "$harness: verify" "npm test red on $branch"; return 1; }
  local total; total=$(total_for "$repo")
  [ "$total" = '$100.00' ] || { bad "$harness: fix" "split 100 3 totals $total"; return 1; }
  ok "$harness: engineer — semantic branch, committed fix + regression test, suite green, total \$100.00"
  if [ "$harness" != codex ]; then
    warn_scan "$harness: engineer demo warning-free" "$log" || true
  fi

  local rlog=/tmp/e2e-$harness-review.log
  local rprompt="You are reviewing someone else's local change. Diff branch $branch against main and judge it against the acceptance criteria in $ISSUE_DOC. Check out $branch, run npm test and 'node bin/split.js 100 3' yourself. Do not edit any file. End with exactly one line: 'VERDICT: PASS' or 'VERDICT: FAIL — <findings>'."
  ( cd "$repo" && launch "$harness" code-review "$rprompt" "$rlog" )
  rc=$?
  [ $rc -ne 0 ] && { bad "$harness: review run" "exit $rc — tail: $(tail -3 "$rlog")"; return 1; }
  grep -q 'VERDICT:' "$rlog" || { bad "$harness: review" "no VERDICT line in review output"; return 1; }
  ok "$harness: adversarial review — $(grep -o 'VERDICT:.*' "$rlog" | head -1)"
}

# --- forge mode: the real thing against a scratch fork ---------------------
forge_leg() {
  local harness=$1 log=/tmp/e2e-forge-$harness.log repo
  note "forge leg: $harness (repo: ${E2E_REPO:-unset})"
  [ -n "${E2E_REPO:-}" ] && [ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ] \
    || { skip "forge/$harness" "set E2E_REPO and GH_TOKEN"; return 0; }
  cred_for "$harness" || { skip "forge/$harness" "no credential in env"; return 0; }
  case "$E2E_REPO" in
    ai-outfitter/outfitter-playground) bad "forge/$harness" "refusing to run against upstream; use a scratch fork"; return 1 ;;
  esac
  # The leg force-pushes; never do that to anything but a playground fork.
  local parent
  parent=$(gh api "repos/$E2E_REPO" --jq '.parent.full_name // ""' 2>/dev/null)
  [ "$parent" = ai-outfitter/outfitter-playground ] \
    || { bad "forge/$harness" "$E2E_REPO is not a fork of ai-outfitter/outfitter-playground; refusing to force-reset it"; return 1; }

  # Reset the scratch fork to the upstream state — the README reset, automated.
  local up; up=$(mktemp -d)
  git clone -q "$E2E_SRC" "$up/playground" && cd "$up/playground" || return 1
  git push -q --force "https://x-access-token:${GH_TOKEN:-$GITHUB_TOKEN}@github.com/$E2E_REPO.git" main:main \
    || { bad "forge/$harness: reset" "force-push to $E2E_REPO failed"; return 1; }
  gh pr list -R "$E2E_REPO" --state open --json number --jq '.[].number' 2>/dev/null \
    | xargs -rn1 gh pr close -R "$E2E_REPO" --delete-branch >/dev/null 2>&1
  ok "forge/$harness: scratch fork reset"

  repo=$(mktemp -d)/playground
  git clone -q "https://x-access-token:${GH_TOKEN:-$GITHUB_TOKEN}@github.com/$E2E_REPO.git" "$repo" || return 1
  ( cd "$repo" && outfitter sync >/dev/null 2>&1 )

  local issue
  issue=$(cd "$repo" && gh issue create -R "$E2E_REPO" \
    --title "split loses cents on uneven amounts" --body-file "$ISSUE_DOC" \
    | grep -oE '[0-9]+$') || { bad "forge/$harness: issue" "gh issue create failed"; return 1; }
  ok "forge/$harness: issue #$issue filed"

  ( cd "$repo" && launch "$harness" engineer "Work issue #$issue in this repository ($E2E_REPO). Follow AGENTS.md. Open the pull request as a draft, get CI green, then mark it ready. Do not merge." "$log" )
  local rc=$?
  [ $rc -eq 3 ] && { skip "forge/$harness" "$(cat "$log")"; return 0; }
  [ $rc -ne 0 ] && { bad "forge/$harness: engineer run" "exit $rc — tail: $(tail -3 "$log")"; return 1; }

  local pr
  pr=$(gh pr list -R "$E2E_REPO" --state open --json number --jq '.[0].number' 2>/dev/null)
  [ -n "$pr" ] && [ "$pr" != null ] || { bad "forge/$harness: PR" "no open pull request after engineer run"; return 1; }
  gh pr view "$pr" -R "$E2E_REPO" --json body,title --jq '.body + .title' | grep -q "#$issue" \
    || bad "forge/$harness: PR" "PR #$pr does not reference issue #$issue"
  local tries=0
  until gh pr checks "$pr" -R "$E2E_REPO" --watch >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -ge 6 ] && { bad "forge/$harness: CI" "checks red or never appeared on PR #$pr"; return 1; }
    sleep 10
  done
  [ "$(gh pr view "$pr" -R "$E2E_REPO" --json isDraft --jq .isDraft)" = false ] \
    || { bad "forge/$harness: PR" "PR #$pr still draft after green CI"; return 1; }
  ok "forge/$harness: PR #$pr open, references #$issue, CI green, marked ready"

  local rlog=/tmp/e2e-forge-$harness-review.log
  ( cd "$repo" && launch "$harness" code-review "Review pull request #$pr in $E2E_REPO against issue #$issue's acceptance criteria. Submit a formal review: REQUEST_CHANGES if anything blocks, otherwise COMMENT. Never APPROVE." "$rlog" )
  rc=$?
  [ $rc -ne 0 ] && { bad "forge/$harness: review run" "exit $rc — tail: $(tail -3 "$rlog")"; return 1; }
  local reviews
  reviews=$(gh api "repos/$E2E_REPO/pulls/$pr/reviews" --jq length 2>/dev/null || echo 0)
  [ "$reviews" -ge 1 ] || { bad "forge/$harness: review" "no formal review submitted on PR #$pr"; return 1; }
  ok "forge/$harness: formal review submitted — PR #$pr is ready for a human merge"
}

# --- main ------------------------------------------------------------------
note "playground-e2e  target=$TARGET mode=$MODE src=$E2E_SRC"
for tool in outfitter git node gh; do
  command -v "$tool" >/dev/null || { echo "missing tool: $tool" >&2; exit 1; }
done

repo=$(fresh_clone) || { echo "cannot clone $E2E_SRC" >&2; exit 1; }
static_checks "$repo"

if [ "$TARGET" != check ] && [ ${#FAIL[@]} -eq 0 ]; then
  legs=$TARGET; [ "$TARGET" = all ] && legs="pi claude codex"
  for harness in $legs; do
    command -v claude >/dev/null || [ "$harness" != claude ] || { skip claude "claude CLI not installed"; continue; }
    command -v codex  >/dev/null || [ "$harness" != codex ]  || { skip codex "codex CLI not installed"; continue; }
    if [ "$MODE" = forge ]; then forge_leg "$harness"; else local_leg "$harness"; fi
  done
fi

note "summary: ${#PASS[@]} passed, ${#FAIL[@]} failed, ${#SKIP[@]} skipped"
for f in ${FAIL[@]+"${FAIL[@]}"}; do echo "  FAIL $f"; done
for s in ${SKIP[@]+"${SKIP[@]}"}; do echo "  SKIP $s"; done
[ ${#FAIL[@]} -eq 0 ]
