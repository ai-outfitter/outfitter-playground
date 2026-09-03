Splitting $100.00 among 3 people loses a cent: every share is floored to
$33.33, so the shares total $99.99 and nobody pays the last cent.

## Reproduce

```sh
node bin/split.js 100 3
```

Output today:

```text
person 1: $33.33
person 2: $33.33
person 3: $33.33
total:    $99.99
```

The bug is the `Math.floor` share in `src/split.js`: the remainder cents
after integer division are dropped instead of being distributed.

## Acceptance criteria

- `node bin/split.js 100 3` prints shares that total exactly `$100.00`
  (e.g. `$33.34, $33.33, $33.33` — how the extra cents are assigned is the
  implementer's choice, but shares MUST differ by at most one cent).
- `split(amount, people)` returns shares whose sum equals the input amount
  for every valid input, not just this example.
- A regression test covering an uneven split (such as `split(100, 3)`)
  is added to `test/split.test.js` and asserts the shares sum to the amount.
- `npm test` passes.
