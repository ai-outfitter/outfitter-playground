# Playground

One pass through this repository teaches you how to use
[Outfitter](https://github.com/ai-outfitter/outfitter): you end with a fork
whose committed [`.agents/`](.agents/settings.yml) directory gave you a full
agent roster from one pinned
[community catalog](https://github.com/ai-outfitter/community-profiles) — no
per-laptop setup — and you will have watched that roster run a real software
development lifecycle against a seeded bug: a scoped issue, an implementation
on a semantic branch, a CI-gated draft pull request, a cold-context
adversarial review, and a pull request left ready for you — the human — to
merge. Then you reset the fork and run it again, with a different harness,
prompt, or division of labor.

1. **Fork** — <https://github.com/ai-outfitter/outfitter-playground/fork>
2. **Check out your fork** (needs [Node.js](https://nodejs.org) 20+ and
   [`gh`](https://cli.github.com/)):

   ```sh
   gh repo fork ai-outfitter/outfitter-playground --clone && cd outfitter-playground
   gh repo edit --enable-issues   # forks start with issues turned off
   node bin/split.js 100 3   # totals $99.99 — there's the seeded bug
   npm test                  # green: the suite misses the case
   ```

3. **Start Outfitter** — sync the pinned catalog, then launch. Pass
   `--harness claude` or `--harness codex` to run the same composed profile
   in a different harness, and on your first run in a harness type `/login`
   at its prompt to set up a model provider before pasting anything:

   ```sh
   npm install -g @ai-outfitter/outfitter
   outfitter sync
   outfitter run   # starts the engineer: .agents/settings.yml sets default_agent
   ```

4. **Paste this prompt:**

   ```text
   Splitting $100 among 3 people loses a cent — `node bin/split.js 100 3`
   totals $99.99. File one scoped issue on this repository with acceptance
   criteria a reviewer can check mechanically (the report in
   docs/issues/0001-split-loses-cents.md is the template), then work that
   issue. Do not merge.
   ```

5. **Watch the SDLC happen.** The engineer's loadout carries the lifecycle:
   it files the issue, fixes `src/split.js` on a `fix/...` branch with a
   conventional commit, adds the regression test the issue demands, verifies
   with `npm test`, opens the pull request as a draft, waits for CI to go
   green, and marks it ready. Ready is the signal that requests review.
6. **Run the adversarial review** — a fresh session, a distinct reviewer
   agent, no stake in the change passing:

   ```sh
   outfitter run code-review
   ```

   ```text
   Review the open pull request against its linked issue's acceptance
   criteria.
   ```

   Expect a formal PR review: one inline comment per finding,
   `REQUEST_CHANGES` if anything blocks, a `COMMENT` verdict when clean —
   never `APPROVE`, because approval is yours. If it found blockers, send
   the findings back through `outfitter run engineer` and review again.
7. **Merge the ready PR.** Verify the acceptance criteria yourself, then
   merge:

   ```sh
   node bin/split.js 100 3   # total must read $100.00
   npm test
   gh pr merge --squash
   ```

That loop — issue → implementation → adversarial review → human merge — is
the whole lesson. [docs/workflows/engineer.md](docs/workflows/engineer.md)
walks the same loop with more control at each step, including delegating the
issue-writing to `git-forge-delegator` and swapping yourself into either
lane.

## Reset and go again

Throw away the run and restore your fork to the upstream state:

```sh
git checkout main
git fetch upstream && git reset --hard upstream/main
git push --force origin main
git branch | grep -v ' main$' | xargs -r git branch -D   # local branches
gh pr list --state open --json number --jq '.[].number' \
  | xargs -rn1 gh pr close --delete-branch                # open PRs + branches
```

Closed issues and merged PRs stay in your fork's history — that is fine; the
next run starts from a fresh issue. (No `upstream` remote?
`git remote add upstream https://github.com/ai-outfitter/outfitter-playground.git`.)

## The exhibit

`split` is a zero-dependency Node CLI that splits a bill among people. Its
bug is deliberate: shares are floored, so uneven amounts lose cents while
the six-test suite stays green — fixing it requires both a code change and a
regression test, which gives the reviewer something real to check. The bug
report with acceptance criteria is seeded at
[docs/issues/0001-split-loses-cents.md](docs/issues/0001-split-loses-cents.md).

> [!NOTE]
> The bug stays unfixed **upstream on purpose** — it is the exhibit. Fix it
> in your fork as often as you like; pull requests fixing it here will be
> declined with thanks.

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

## Demo it in a container

[e2e/](e2e/README.md) wires everything you already have — `gh auth token`,
your fork (created and force-reset for you), your Claude Code/Codex logins —
into a container, two ways: `e2e/demo.sh` drops you into an interactive
Outfitter session with the demo script printed, ready to run the flow live;
`e2e/test.sh` runs the whole flow automatically while you watch.
`e2e/test.sh check` is a free sanity pass (no model calls) asserting the
repo demos cleanly: zero Outfitter warnings, all agents resolved from
community-profiles.

```sh
e2e/demo.sh    # you drive it
e2e/test.sh    # it drives itself
```

## License

[MIT](LICENSE.md)
