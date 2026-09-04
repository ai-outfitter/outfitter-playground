#!/usr/bin/env bash
set -eu

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(git -C "$script_dir" rev-parse --show-toplevel)
test_root=$(mktemp -d "${TMPDIR:-/tmp}/outfitter-demo-auth-test.XXXXXX")
cleanup() { rm -rf -- "$test_root"; }
trap cleanup EXIT

real_git=$(command -v git)
real_npm=$(command -v npm)
stub_bin="$test_root/bin"
runtime_root="$test_root/runtime"
mkdir -p "$stub_bin" "$runtime_root/bin"

printf '%s\n' \
  '#!/usr/bin/env bash' \
  'if [ "${1:-}" = prefix ] && [ "${2:-}" = -g ]; then' \
  '  printf "%s\n" "$FAKE_NPM_PREFIX"' \
  '  exit 0' \
  'fi' \
  'exec "$REAL_NPM" "$@"' \
  > "$stub_bin/npm"

printf '%s\n' \
  '#!/usr/bin/env bash' \
  'case " $* " in' \
  '  *" fetch "*|*" checkout "*|*" reset "*|*" clean "*|*" push "*|*" worktree remove "*|*" branch -qD "*)' \
  '    printf "%s\n" "$*" >> "$DESTRUCTIVE_GIT_LOG"' \
  '    exit 97' \
  '    ;;' \
  'esac' \
  'exec "$REAL_GIT" "$@"' \
  > "$stub_bin/git"

printf '%s\n' \
  '#!/usr/bin/env bash' \
  'printf "%s\n" "$*" >> "$GH_CALL_LOG"' \
  'case "$GH_MODE:$*" in' \
  '  invalid:"auth token") printf "%s\n" invalid-test-token; exit 0 ;;' \
  '  valid:"auth token") printf "%s\n" valid-test-token; exit 0 ;;' \
  '  valid:"api user") exit 0 ;;' \
  '  valid:api\ "repos/"*" --jq "*) printf "%s\n" ai-outfitter/outfitter-playground; exit 0 ;;' \
  '  valid:repo\ set-default\ *) exit 0 ;;' \
  'esac' \
  'exit 1' \
  > "$stub_bin/gh"

printf '%s\n' \
  '#!/usr/bin/env bash' \
  'printf "%s\n" "$*" >> "$OUTFITTER_CALL_LOG"' \
  'case " $* " in' \
  '  *" run auth-check "*)' \
  '    if [ "${GH_TOKEN+x}" = x ] || [ "${GITHUB_TOKEN+x}" = x ] || [ "${GITHUB_PERSONAL_ACCESS_TOKEN+x}" = x ]; then' \
  '      echo "unexpected GitHub credential in provider probe" >&2' \
  '      exit 88' \
  '    fi' \
  '    echo "provider unavailable" >&2' \
  '    exit 42' \
  '    ;;' \
  'esac' \
  'if [ "${GH_TOKEN+x}" = x ] || [ "${GITHUB_TOKEN+x}" = x ] || [ "${GITHUB_PERSONAL_ACCESS_TOKEN+x}" = x ]; then' \
  '  echo "unexpected GitHub credential in check mode" >&2' \
  '  exit 88' \
  'fi' \
  'case "${1:-}" in' \
  '  sync) printf "%s\n" "catalog synced" ;;' \
  '  validate) ;;' \
  '  list)' \
  '    printf "%s\n" "  engineer  [github:ai-outfitter/community-profiles#v1.7.0]"' \
  '    printf "%s\n" "  git-forge-delegator  [github:ai-outfitter/community-profiles#v1.7.0]"' \
  '    ;;' \
  '  *) echo "unexpected outfitter call: $*" >&2; exit 89 ;;' \
  'esac' \
  > "$runtime_root/bin/outfitter"

# The hosted GitHub MCP preflight is one curl handshake; answer it with a
# canned status so no test case touches the network.
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'printf "%s\n" "$*" >> "$CURL_CALL_LOG"' \
  'printf "%s" "${HOSTED_MCP_STATUS:-200}"' \
  > "$stub_bin/curl"

# Never read the host Keychain from a test; the claude cases carry a token in.
printf '%s\n' '#!/usr/bin/env bash' 'exit 1' > "$stub_bin/security"

chmod +x "$stub_bin/npm" "$stub_bin/git" "$stub_bin/gh" "$stub_bin/curl" "$stub_bin/security" "$runtime_root/bin/outfitter"
export CLAUDE_CODE_OAUTH_TOKEN=test-claude-token
export REAL_GIT="$real_git" REAL_NPM="$real_npm" FAKE_NPM_PREFIX="$runtime_root"
export PATH="$stub_bin:$PATH"

run_check_case() {
  mode=$1
  case_root="$test_root/check-$mode"
  mkdir -p "$case_root/host-home"
  export GH_MODE="$mode"
  export GH_CALL_LOG="$case_root/gh.log"
  export OUTFITTER_CALL_LOG="$case_root/outfitter.log"
  export DESTRUCTIVE_GIT_LOG="$case_root/destructive-git.log"

  output=$(cd "$repo_root" && HOME="$case_root/host-home" \
    PLAYGROUND_HOME="$case_root/demo-home" \
    GH_TOKEN=ambient-invalid GITHUB_TOKEN=ambient-invalid \
    GITHUB_PERSONAL_ACCESS_TOKEN=ambient-invalid \
    bash e2e/demo.sh check 2>&1) || {
      echo "$output" >&2
      echo "FAIL  check mode with $mode GitHub CLI auth" >&2
      exit 1
    }
  [ ! -s "$GH_CALL_LOG" ] || {
    echo "FAIL  check mode called gh with $mode auth" >&2
    cat "$GH_CALL_LOG" >&2
    exit 1
  }
  [ ! -s "$DESTRUCTIVE_GIT_LOG" ] || {
    echo "FAIL  check mode ran a destructive git command" >&2
    cat "$DESTRUCTIVE_GIT_LOG" >&2
    exit 1
  }
  expected=$(printf '%s\n' 'sync' 'validate --strict' 'list')
  actual=$(cat "$OUTFITTER_CALL_LOG")
  [ "$actual" = "$expected" ] || {
    echo "FAIL  unexpected check-mode Outfitter calls" >&2
    printf 'expected:\n%s\nactual:\n%s\n' "$expected" "$actual" >&2
    exit 1
  }
  echo "PASS  check mode ignores $mode GitHub CLI auth"
}

run_live_failure_case() {
  mode=$1
  harness=$2
  case_root="$test_root/live-$harness-$mode"
  mkdir -p "$case_root/host-home"
  export GH_MODE="$mode"
  export GH_CALL_LOG="$case_root/gh.log"
  export OUTFITTER_CALL_LOG="$case_root/outfitter.log"
  export DESTRUCTIVE_GIT_LOG="$case_root/destructive-git.log"

  if output=$(cd "$repo_root" && HOME="$case_root/host-home" \
    PLAYGROUND_HOME="$case_root/demo-home" bash e2e/demo.sh "$harness" 2>&1); then
    echo "FAIL  $harness mode accepted $mode GitHub CLI auth" >&2
    exit 1
  fi
  [ ! -s "$DESTRUCTIVE_GIT_LOG" ] || {
    echo "FAIL  $harness mode reached destructive reset with $mode auth" >&2
    cat "$DESTRUCTIVE_GIT_LOG" >&2
    exit 1
  }
  [ ! -s "$OUTFITTER_CALL_LOG" ] || {
    echo "FAIL  $harness mode invoked Outfitter before rejecting $mode auth" >&2
    cat "$OUTFITTER_CALL_LOG" >&2
    exit 1
  }
  case "$mode:$output" in
    absent:*"gh is not authenticated"*) ;;
    invalid:*"gh authentication is invalid"*) ;;
    *) echo "FAIL  wrong $harness-mode error for $mode auth" >&2; echo "$output" >&2; exit 1 ;;
  esac
  echo "PASS  $harness mode rejects $mode GitHub CLI auth before reset"
}

assert_no_destructive_git() {
  case_name=$1
  [ ! -s "$DESTRUCTIVE_GIT_LOG" ] || {
    echo "FAIL  $case_name reached destructive reset" >&2
    cat "$DESTRUCTIVE_GIT_LOG" >&2
    exit 1
  }
}

run_live_mcp_failure_case() {
  case_root="$test_root/live-pi-hosted-mcp-rejected"
  mkdir -p "$case_root/host-home"
  export GH_MODE=valid
  export GH_CALL_LOG="$case_root/gh.log"
  export CURL_CALL_LOG="$case_root/curl.log"
  export OUTFITTER_CALL_LOG="$case_root/outfitter.log"
  export DESTRUCTIVE_GIT_LOG="$case_root/destructive-git.log"

  if output=$(cd "$repo_root" && HOME="$case_root/host-home" \
    PLAYGROUND_HOME="$case_root/demo-home" HOSTED_MCP_STATUS=401 \
    bash e2e/demo.sh outfitter 2>&1); then
    echo "FAIL  outfitter mode accepted a token the hosted GitHub MCP rejects" >&2
    exit 1
  fi
  case "$output" in
    *"rejected the gh token: HTTP 401"*) ;;
    *) echo "FAIL  wrong hosted-MCP error" >&2; echo "$output" >&2; exit 1 ;;
  esac
  grep -q -- '-H Authorization: Bearer valid-test-token' "$CURL_CALL_LOG" || {
    echo "FAIL  hosted-MCP probe did not present the gh token" >&2
    cat "$CURL_CALL_LOG" >&2
    exit 1
  }
  assert_no_destructive_git "hosted-MCP failure"
  [ ! -s "$OUTFITTER_CALL_LOG" ] || {
    echo "FAIL  hosted-MCP case invoked Outfitter" >&2
    cat "$OUTFITTER_CALL_LOG" >&2
    exit 1
  }
  echo "PASS  outfitter mode rejects a token the hosted GitHub MCP refuses before reset"
}

run_live_provider_failure_case() {
  case_root="$test_root/live-pi-provider-failure"
  mkdir -p "$case_root/host-home/.pi/agent"
  printf '%s\n' '{"defaultProvider":"test-provider","defaultModel":"test-model"}' \
    > "$case_root/host-home/.pi/agent/settings.json"
  export GH_MODE=valid
  export GH_CALL_LOG="$case_root/gh.log"
  export CURL_CALL_LOG="$case_root/curl.log"
  export OUTFITTER_CALL_LOG="$case_root/outfitter.log"
  export DESTRUCTIVE_GIT_LOG="$case_root/destructive-git.log"

  if output=$(cd "$repo_root" && HOME="$case_root/host-home" \
    PLAYGROUND_HOME="$case_root/demo-home" bash e2e/demo.sh outfitter 2>&1); then
    echo "FAIL  outfitter mode accepted a failed provider probe" >&2
    exit 1
  fi
  case "$output" in
    *"demo arena was not reset"*) ;;
    *) echo "FAIL  wrong provider-probe error" >&2; echo "$output" >&2; exit 1 ;;
  esac
  assert_no_destructive_git "provider-probe failure"
  expected='run auth-check --harness pi -- --provider test-provider --model test-model -p Reply with exactly OUTFITTER_AUTH_OK.'
  actual=$(cat "$OUTFITTER_CALL_LOG")
  [ "$actual" = "$expected" ] || {
    echo "FAIL  unexpected provider-probe Outfitter calls" >&2
    printf 'expected:\n%s\nactual:\n%s\n' "$expected" "$actual" >&2
    exit 1
  }
  echo "PASS  pi provider failure leaves the arena unreset and withholds GitHub credentials"
}

run_check_case absent
run_check_case invalid
for harness in outfitter claude codex; do
  run_live_failure_case absent "$harness"
  run_live_failure_case invalid "$harness"
done
run_live_mcp_failure_case
run_live_provider_failure_case
