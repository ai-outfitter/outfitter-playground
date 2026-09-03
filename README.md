# Playground

A self-contained sandbox for practicing agentic engineering workflows with
[Outfitter](https://github.com/ai-outfitter/outfitter) and the
[community-profiles](https://github.com/ai-outfitter/community-profiles)
catalog. Fork it, run a workflow against a known bug, reset, run a different
one.

The repository ships three things:

- **An exhibit app** — `split`, a zero-dependency Node CLI that splits a bill
  among people, with a deliberately unfixed bug: uneven amounts lose cents
  (`node bin/split.js 100 3` totals `$99.99`). Its tests pass; they just
  don't cover the case. The bug report with acceptance criteria is seeded at
  [docs/issues/0001-split-loses-cents.md](docs/issues/0001-split-loses-cents.md).
- **A preconfigured [`.agents/`](.agents/settings.yml)** — pinned to the
  community-profiles catalog, so `outfitter sync` gives you the `engineer`,
  `code-review`, and `git-forge-delegator` agents with no setup.
- **A workflow walkthrough** —
  [docs/workflows/engineer.md](docs/workflows/engineer.md) runs the loop this
  repo exists to teach: scoped issue → implementation on a branch → draft PR
  gated on CI → cold-context adversarial review → human merge.

> [!NOTE]
> The bug stays unfixed **upstream on purpose** — it is the exhibit. Fix it
> in your fork as often as you like; pull requests fixing it here will be
> declined with thanks.

## Prerequisites

- [Node.js](https://nodejs.org) 20+ (the app and its tests need nothing else)
- [`gh`](https://cli.github.com/) authenticated to your GitHub account
- [`outfitter`](https://github.com/ai-outfitter/outfitter):
  `npm install -g @ai-outfitter/outfitter` (or `npx @ai-outfitter/outfitter`)
- At least one agent harness: [Pi](https://github.com/earendil-works/pi-coding-agent)
  (bundled with Outfitter), Claude Code, or Codex CLI

## Fork, run, reset

**Fork** — work in your own fork so agents can push branches and open pull
requests freely:

```sh
gh repo fork ai-outfitter/playground --clone
cd playground
npm test                     # green — the bug is uncovered, not failing
node bin/split.js 100 3      # $99.99: there's the exhibit
outfitter sync               # fetch the pinned community catalog
```

**Run** — issues do not travel with forks, so seed the bug report first:

```sh
gh issue create \
  --title "split loses cents on uneven amounts" \
  --body-file docs/issues/0001-split-loses-cents.md
```

then follow [the engineer workflow](docs/workflows/engineer.md), or improvise:
implement by hand and have an agent review, delegate the issue and review by
hand, or swap harnesses (`outfitter run engineer --harness claude`).

**Reset** — throw away the run and restore your fork to the upstream state,
ready for the next experiment:

```sh
git checkout main
git fetch upstream && git reset --hard upstream/main
git push --force origin main
git branch | grep -v ' main$' | xargs -r git branch -D   # local branches
gh pr list --state open --json number --jq '.[].number' \
  | xargs -rn1 gh pr close --delete-branch                # open PRs + branches
```

Closed issues and merged PRs stay in your fork's history — that is fine; the
next run starts from a fresh issue. (No `upstream` remote? `gh repo fork
--clone` adds it; otherwise
`git remote add upstream https://github.com/ai-outfitter/playground.git`.)

## The exhibit app

```text
usage: split <amount> <people>

$ node bin/split.js 89.97 3
person 1: $29.99
person 2: $29.99
person 3: $29.99
total:    $89.97
```

`npm test` runs the suite with `node --test`. No dependencies, no build step.

## Layout

```text
.agents/settings.yml     Outfitter settings: pinned community-profiles source
docs/issues/             seeded bug reports to file with `gh issue create`
docs/workflows/          workflow walkthroughs
src/split.js             the library (the bug lives here)
bin/split.js             the CLI
test/split.test.js       the suite that passes anyway
AGENTS.md                repository instructions agents follow (CLAUDE.md symlinks to it)
```

## License

[MIT](LICENSE.md)
