---
name: issue-first
description: >-
  File one scoped forge issue before implementing any reported bug or
  feature that no open issue tracks yet, then work that issue.
---

# Issue first

Work arrives as reports, not instructions. The forge issue is the durable
record: it outlives the session, carries the acceptance criteria, and is
what the pull request closes.

When you receive a bug report or feature request that no open issue on this
repository tracks yet:

1. Reproduce the report first. Run the command it names and confirm the
   behavior; say plainly if you could not.
2. File ONE scoped issue (`gh issue create`) before writing any code:
   - a title naming the defect, not the fix;
   - a body with the reproduction command and its observed output;
   - acceptance criteria a reviewer can check mechanically — name the
     command that proves the work and its expected output.
   If the repository seeds a matching report under `docs/issues/`, use that
   file as the issue body (`--body-file`).
3. Work that issue: implement on a semantic branch whose pull request
   references the issue it closes.
4. Several unrelated problems are several issues. Never batch them into one.

If an open issue already tracks the report, skip filing and work it.
