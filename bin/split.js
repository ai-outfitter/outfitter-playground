#!/usr/bin/env node
import { split, formatDollars } from "../src/split.js";

const usage = "usage: split <amount> <people>";
const example = "example: split 89.97 3";
const args = process.argv.slice(2);

if (args.includes("--help")) {
  console.log(usage);
  console.log(example);
  process.exit(0);
}

const [amountArg, peopleArg] = args;
if (amountArg === undefined || peopleArg === undefined) {
  console.error(usage);
  console.error(example);
  process.exit(2);
}

const shares = split(Number(amountArg), Number(peopleArg));
shares.forEach((share, i) => {
  console.log(`person ${i + 1}: ${formatDollars(share)}`);
});
const total = shares.reduce((sum, share) => sum + share, 0);
console.log(`total:    ${formatDollars(total)}`);
