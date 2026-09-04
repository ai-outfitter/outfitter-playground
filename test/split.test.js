import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { split, formatDollars } from "../src/split.js";

test("splits an even amount equally", () => {
  assert.deepEqual(split(90, 3), [30, 30, 30]);
});

test("splits between two people", () => {
  assert.deepEqual(split(25.5, 2), [12.75, 12.75]);
});

test("one person pays the whole bill", () => {
  assert.deepEqual(split(42.42, 1), [42.42]);
});

test("rejects a negative amount", () => {
  assert.throws(() => split(-5, 2), RangeError);
});

test("rejects a non-integer number of people", () => {
  assert.throws(() => split(10, 2.5), RangeError);
  assert.throws(() => split(10, 0), RangeError);
});

test("formats dollars with two decimals", () => {
  assert.equal(formatDollars(12.5), "$12.50");
});

test("prints an even split as JSON in either flag position", () => {
  const expected =
    '{"amount":100,"people":4,"shares":[25,25,25,25],"total":100}\n';

  assert.equal(
    execFileSync(process.execPath, ["bin/split.js", "100", "4", "--json"], {
      encoding: "utf8",
    }),
    expected,
  );
  assert.equal(
    execFileSync(process.execPath, ["bin/split.js", "--json", "100", "4"], {
      encoding: "utf8",
    }),
    expected,
  );
});
