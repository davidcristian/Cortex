# Readings: shuffled test order

How the shuffled order of each checked suite behaves as a suite grows, and how often a fixed seed
catches a planted order dependency. Cited by
[ADR-0002](../adr/ADR-0002-toolchain-checks.md#test-order), decisions 16 and 17 and the consequences.

## pytest-randomly keeps the existing order when a test is added

**2026-08-16.** In `scripts/` at seed 7919, adding one test file left the other 578 node ids in
the same relative order. Growing an isolated module from eight tests to nine inserted the ninth
and left the eight in their relative order.

Method: `uv run pytest --collect-only -q --randomly-seed=7919` before and after the addition,
comparing the node id lists.

## libtest redraws a binary's whole order when a test is added

**2026-08-17.** A probe binary at seed 104729 ran eight tests as `foxtrot alpha charlie echo delta
bravo golf hotel`; with a ninth added it ran `charlie bravo golf echo foxtrot hotel alpha india
delta`, in which the original eight no longer hold their relative order.

Method: `cargo +nightly test -- -Z unstable-options --shuffle-seed=104729 --test-threads=1` on the
probe binary before and after the addition.

## How often a seed catches a planted pair

A plant is two tests in one file, the first writing a module-level value and the second asserting
it, so the pair passes in one order and fails in the other.

| Date | Suite | Plant | Seeds that failed |
| --- | --- | --- | --- |
| 2026-08-16 | `scripts/` | writer and reader | 11 of 20 |
| 2026-08-16 | overlay (Vitest) | writer and reader | the frozen seed and 2 of 10 others |
| 2026-08-17 | Rust workspace | a `static AtomicBool`, with 58 filler tests between the pair so it is farther apart than the thread count | 10 of 20 |
| 2026-08-17 | `scripts/` | a pair that passes at the frozen seed 7919 | 14 of 40 |

The first `scripts/` plant written did not fail at the frozen seed; renaming its two tests, which
moves their drawn positions, made it fail. The Rust plant passed the stable `cargo test` step of
`just check-body` and failed its nightly coverage step.

Method: plant the pair, then run the suite once per seed (`--randomly-seed`, `--sequence.seed` or
`--shuffle-seed`, or `just shuffle <seed>` for the last row), count the seeds that fail, and remove
the plant.
