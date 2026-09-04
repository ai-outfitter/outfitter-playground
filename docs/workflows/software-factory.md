# The software factory: label an issue, merge a reviewed pull request

This branch runs the community catalog's
[`software-factory` workflow](https://github.com/ai-outfitter/community-profiles/blob/main/workflows/software-factory/workflow.yaml)
inside your repository's own GitHub Actions. Nothing runs on a laptop: you
label an issue, an agent implements it and readies a pull request, a second
cold agent run posts the formal review, and you merge. Compare it with the
[engineer walkthrough](engineer.md), where you drive the same loop from a
local session.

## 0. Put this branch in your copy

Generate your copy with every branch, then make this one the default:

```sh
gh repo create outfitter-playground --template ai-outfitter/outfitter-playground --public --clone --include-all-branches
cd outfitter-playground
gh repo edit --default-branch software-factory
git checkout software-factory
```

Workflows that answer to issue events run only from the default branch, which
is why the branch has to be the default (or merged into `main`).

## 1. Give the factory a model and permission to open pull requests

```sh
gh secret set OPENAI_API_KEY          # paste your key; the agent runs on openai/gpt-5.6-sol
```

Then in **Settings → Actions → General**, enable *Allow GitHub Actions to
create and approve pull requests*. Without it `gh pr create` is refused and
the agent leaves its branch pushed and a comment on the issue saying so. In
an organization that setting can be locked at the organization level
("Write permissions for workflows are disabled by the organization"); an
organization owner enables it under the organization's Actions settings, or
you skip it entirely with `FACTORY_TOKEN` below.

The model lives in one place,
[`.agents/agents/factory-engineer/agent.md`](../../.agents/agents/factory-engineer/agent.md).
To run on another provider, change its `model:` line and pass that
provider's secret in
[`.github/workflows/software-factory.yml`](../../.github/workflows/software-factory.yml).

Optional: a fine-grained personal access token with contents, pull requests,
and issues write, stored as `FACTORY_TOKEN`. Pull requests opened with the
default workflow token never trigger this repository's own `test.yml`; ones
opened with a PAT do, so the agent waits for the check instead of trusting
its own `npm test`.

## 2. File the seeded bug and label it

```sh
gh issue create --title "split loses cents on uneven amounts" --body-file docs/issues/0001-split-loses-cents.md
gh issue edit 1 --add-label software-factory      # create the label first if the repo has none
```

The label is the trigger. Within a minute the run comments on the issue that
it picked the work up, naming the model and agent.

## 3. Watch the run

```sh
gh run watch
```

The `implement` job runs the community `engineer` (as `factory-engineer`,
the overlay that pins the model): it reproduces the bug, fixes
`src/split.js` on a `fix/...` branch, adds the regression test, runs
`npm test`, opens the pull request as a draft with `Closes #1`, marks it
ready, and runs its own adversarial self-review. The job then stamps the
pull request body with the model and agent.

The `review` job starts a second, cold session that did not write the change.
It judges the diff against the issue's acceptance criteria, runs the tests
and its own edge cases, and posts exactly one formal review:
`REQUEST_CHANGES` when something blocks, otherwise a `COMMENT` review
opening with `Verdict: approve`. It never approves; approval is yours.

## 4. Act on the review, then merge

If the review requested changes, send the agent back to the same pull
request:

```sh
gh workflow run software-factory.yml -f issue=1 -f pr=<n> -f step=implement
```

A fresh review follows automatically. To re-review by hand:

```sh
gh workflow run software-factory.yml -f issue=1 -f pr=<n> -f step=review
```

When the verdict is `approve`, verify the acceptance criteria yourself and
merge:

```sh
node bin/split.js 100 3   # total must read $100.00
npm test
gh pr merge <n> --squash
```

## What runs where

| Piece | Where it lives |
| --- | --- |
| Trigger | the `software-factory` label, or `workflow_dispatch` |
| Agents | community catalog `v1.7.0`, pinned in `.agents/settings.yml`; `factory-engineer` overlay in `.agents/agents/` |
| Model | `.agents/agents/factory-engineer/agent.md`, provider in `.agents/models.json` |
| Credentials | `OPENAI_API_KEY` secret; the workflow token, or `FACTORY_TOKEN` |
| Compute | your repository's GitHub-hosted runners |
| Attribution | every comment, pull request, and review ends with the model and agent |

Reset the way the [README](../../README.md#reset-and-go-again) describes,
then label a fresh issue.
