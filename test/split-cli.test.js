// Black-box tests for bin/split.js: the CLI is run as a child process and
// only its output streams and exit status are observed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cli = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "bin",
  "split.js",
);

test("--help prints usage and example to stdout and exits 0", () => {
  const result = spawnSync(process.execPath, [cli, "--help"], {
    encoding: "utf8",
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /^usage: split <amount> <people>$/m);
  assert.match(result.stdout, /^example: split 89\.97 3$/m);
  assert.equal(result.stderr, "");
});

test("--help does not print share or total lines", () => {
  const result = spawnSync(process.execPath, [cli, "--help"], {
    encoding: "utf8",
  });
  assert.doesNotMatch(result.stdout, /person \d|total:/);
});

test("missing arguments print usage to stderr and exit 2", () => {
  const result = spawnSync(process.execPath, [cli], { encoding: "utf8" });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /^usage: split <amount> <people>$/m);
  assert.match(result.stderr, /^example: split 89\.97 3$/m);
  assert.equal(result.stdout, "");
});
