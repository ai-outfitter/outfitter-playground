# Demo the engineer flow

One script, no container. It runs Outfitter under a **persistent, isolated
HOME** at `/tmp/outfitter-playground-home` — your harness logins are copied
in from the host every run (originals untouched), onboarding state and the
synced catalog persist between runs, and your real `~` is never touched.
It runs in this checkout, whose origin must be **your own playground
generated from the template** (the script verifies the lineage and refuses
the org repo itself). Each run resets the checkout to the upstream state —
uncommitted changes and extra branches are discarded — so the seeded bug is
back and issues and PRs land on your copy, never upstream.

```sh
e2e/demo.sh            # engineer session, claude harness
e2e/demo.sh pi         # same flow under pi
e2e/demo.sh codex      # same flow under codex
```

You land in an interactive engineer session with the demo script printed:
paste the prompt, watch it file the issue and work it into a CI-gated,
ready-for-review PR, then exit the session — you stay in a shell inside the
demo environment to run the cold-context review
(`outfitter run code-review --harness <h>`) and merge.

`gh` works via `GH_TOKEN` from `gh auth token`. `ANTHROPIC_API_KEY` /
`OPENAI_API_KEY` are passed through when set (pi needs one of them).

## Other commands

```sh
e2e/demo.sh check      # free, no model calls: bug present, suite green,
                       # sync + validate --strict with zero warnings,
                       # agents resolved from community-profiles
e2e/demo.sh reset      # wipe the demo HOME for a from-scratch start
```

`PLAYGROUND_HOME=<dir>` overrides the demo HOME location.

## Demo the software factory

`e2e/factory.sh` runs the same loop with nothing on your host but `gh`: the
agent runs in your playground's own Actions from the `software-factory`
branch. It makes that branch the arena's default (issue events only reach
the default branch), sets the `OPENAI_API_KEY` secret from your environment
when the arena has none, enables pull-request creation for the workflow
token or falls back to a `FACTORY_TOKEN` secret when the organization locks
it, resets the arena to the upstream state, files the seeded bug with the
`software-factory` label, and watches the run.

```sh
e2e/factory.sh            # reset, file + label the bug, watch the run, print the PR and review
e2e/factory.sh check      # free: bug present, suite green, workflow present, catalog validates
e2e/factory.sh status     # the open factory PR, its checks, and its reviews
e2e/factory.sh review     # dispatch a re-review of the open factory PR
```
