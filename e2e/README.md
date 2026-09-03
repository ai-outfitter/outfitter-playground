# Demo cockpit

One command puts you in a container, inside an interactive Outfitter session,
ready to demo the whole engineer flow live — the agent files the issue,
fixes the seeded bug on a branch, opens a draft PR, CI runs, a cold-context
reviewer delivers a verdict, and you merge:

```sh
e2e/test.sh            # claude harness (default) — or: pi, codex
```

Before you land in the session it wires everything from what you already
have — no env setup:

- `GH_TOKEN` from `gh auth token`
- your **fork** of `ai-outfitter/outfitter-playground`, found by parentage
  (created with `gh repo fork` if missing), **force-reset to the upstream
  state**, open PRs closed, issues enabled — so every demo starts clean
- your Claude Code (`~/.claude`) / Codex (`~/.codex`) logins mounted in;
  `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` forwarded when set
- your git name/email for the commits the agent makes

On landing you get a printed demo script: the prompt to paste into the
engineer, what to watch for, then `outfitter run code-review` for the
adversarial review, then the merge commands. Exiting the engineer session
drops you into a shell in the clone to run those next steps. Exit the shell
to end the demo; run `e2e/test.sh` again for a fresh slate.

The image is the published `ghcr.io/ai-outfitter/outfitter` base plus `gh`
and the claude/codex CLIs (pi ships with Outfitter). Rootless podman is
handled (`--userns=keep-id`).

## Free sanity check

```sh
e2e/test.sh check
```

No model calls: clones the repo, confirms the bug reproduces and the suite
is green, runs `outfitter sync` and `outfitter validate --strict` asserting
**zero warnings**, and confirms `engineer`, `code-review`, and
`git-forge-delegator` resolve from the pinned community-profiles catalog —
the "does this demo cleanly for a new user" gate.

## Headless mode (CI use)

`run.sh` (the image's default entrypoint) can also drive the flow
non-interactively for automation: `local` legs implement + review in-repo
with no forge writes, and `--forge` legs run the full issue → PR → CI →
formal-review loop against a fork named in `E2E_REPO`, force-resetting it
first (it refuses upstream and anything that is not a playground fork).
Agent output streams through and is scanned for warnings. See the header of
[run.sh](run.sh) for flags; the demo cockpit above is the primary interface.
