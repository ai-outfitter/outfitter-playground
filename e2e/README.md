# End-to-end tests

Prove the engineer flow works, per harness, from a clean slate — where
"works" means what a new user would experience: **zero warnings** from
`outfitter sync` / `validate --strict` / `list`, agents provably composed
from the **community-profiles** catalog, and the loop itself — issue →
implementation → adversarial review → a PR ready to merge — completing
against the seeded bug. Every leg starts from a fresh clone (local mode) or
a force-reset scratch fork (forge mode), so runs are repeatable.

## Quick start

One command runs the whole workflow — issue filed, engineer solves it, draft
PR, CI, cold-context review, merge-ready PR — against **your fork** of the
playground (created for you if missing, force-reset to upstream first),
using the credentials you already have: `gh auth token` for the forge, your
Claude Code / Codex logins mounted from `~/.claude` / `~/.codex`:

```sh
e2e/test.sh            # default: claude harness
e2e/test.sh pi         # or codex, or all, or check
```

## By hand

```sh
docker build -t playground-e2e e2e

# Free smoke check — no model calls: tools present, exhibit intact,
# sync/validate warning-free, catalog attribution correct.
docker run --rm playground-e2e check

# One harness, local mode (implement + review, no forge writes):
docker run --rm -e ANTHROPIC_API_KEY playground-e2e claude

# Every harness with a credential present:
docker run --rm -e ANTHROPIC_API_KEY -e OPENAI_API_KEY playground-e2e all
```

`podman` works the same. To test local changes instead of upstream, mount
your checkout: `-v "$PWD:/src:ro"`.

## Full forge mode

Runs the real flow — issue filed with `gh`, draft PR, CI, formal review —
against a **scratch fork you own** (never upstream; the script refuses).
The scratch fork is force-reset to the upstream state before each leg:

```sh
docker run --rm \
  -e ANTHROPIC_API_KEY \
  -e GH_TOKEN \
  -e E2E_REPO=<you>/playground \
  playground-e2e claude --forge
```

The leg asserts: issue filed → open PR referencing it → CI green → PR
marked ready → at least one formal review submitted → summary line
declaring the PR ready for a human merge.

## What each leg asserts

| Check | Local | Forge |
| --- | --- | --- |
| Exhibit bug present, baseline suite green | ✓ | ✓ |
| `sync` / `validate --strict` with zero warnings | ✓ | ✓ |
| `engineer`, `code-review`, `git-forge-delegator` attributed to `github:ai-outfitter/community-profiles#<ref>` | ✓ | ✓ |
| Semantic `fix/` branch, conventional commit, nothing left uncommitted | ✓ | via PR |
| `test/split.test.js` gained a regression test | ✓ | via review |
| `npm test` green and `split 100 3` totals `$100.00` after the fix | ✓ | via CI |
| Cold-context review delivers a verdict | `VERDICT:` line | formal PR review |
| Issue → draft PR → CI → ready → reviewed | — | ✓ |

## Harness notes

- **pi** — bundled with Outfitter. Picks `--provider anthropic --model
  *sonnet*` when `ANTHROPIC_API_KEY` is set, else openai; override with
  `E2E_PI_ARGS`.
- **claude** — headless `-p` with `--dangerously-skip-permissions`, which the
  script only allows inside a container.
- **codex** — `codex exec` with sandbox bypass (container-only, same guard).
  Runs without `--strict` because Codex cannot project the composed agent
  identity yet; expect Outfitter to warn about the dropped identity. The leg
  still exercises the flow, but this is a known demo gap, not a playground
  bug.

`E2E_TIMEOUT` (default 900s) bounds each agent run. Logs land in
`/tmp/e2e-*.log` inside the container; add `-v /tmp/e2e-logs:/tmp` to keep
them.
