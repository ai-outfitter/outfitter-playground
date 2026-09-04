#!/usr/bin/env node
import { split, formatDollars } from "../src/split.js";

const args = process.argv.slice(2);
const json = args.includes("--json");
const [amountArg, peopleArg] = args.filter((arg) => arg !== "--json");
if (amountArg === undefined || peopleArg === undefined) {
  console.error("usage: split <amount> <people>");
  console.error("example: split 89.97 3");
  process.exit(2);
}

const amount = Number(amountArg);
const people = Number(peopleArg);
const shares = split(amount, people);
const total = shares.reduce((sum, share) => sum + share, 0);

if (json) {
  console.log(JSON.stringify({ amount, people, shares, total }));
} else {
  shares.forEach((share, i) => {
    console.log(`person ${i + 1}: ${formatDollars(share)}`);
  });
  console.log(`total:    ${formatDollars(total)}`);
}
