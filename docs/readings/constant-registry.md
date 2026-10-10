# Readings: the constant registry

How often the values the cross-tree constant registry holds appear in the tree outside the places it
registers, and which line the failure names when a search text is not found. Cited by
[ADR-0042](../adr/ADR-0042-cross-tree-constant-registry.md), decision 21 (no census of values
written outside the registry) and decision 23 (the per-line reading). The registry's own size is not
recorded here: `crosscheck.py` prints it on every passing run.

## Uncovered occurrences of registered values

**2026-08-23.** Every registered value was rendered in all three forms a mention can use and matched
as a bounded token over every tracked text file, with the occurrences the registry's search texts
already cover subtracted.

| occurrences | where |
|---|---|
| 37,717 | every tracked text file |
| 927 | files that also contain the constant's identifier |
| 34 | one entry sorted exhaustively by hand, of which three were real far sides |

Most uncovered occurrences are unrelated numbers that share digits with a registered value, which is
why finding far sides is done by sorting on the name a value is written under.

Method: `git ls-files` less lockfiles and the overlay's node tree, each value rendered through
`values.py` and searched with `searchtexts.bounded`, the covered spans from the registry's mentions
subtracted.

## Which line a fault names

**2026-09-17.** A scratch replay took the 308 distinct single-line search texts the registry
rendered and changed each of their 418 bounded occurrences in turn, recomputing every line's
reading. Each cell is the cases where the reading named the changed line, then those where it named
one unique line at all, then the cases. A deletion has no line to find, so any line named for it is
a sibling.

| Change to one occurrence | Opening run per line | Both ends, unique best | Both ends, at least half |
| --- | --- | --- | --- |
| last character of the value | 310 of 351 | 329 / 337 / 351 | 329 / 337 / 351 |
| first character of the search text | 10 of 418 | 398 / 402 / 418 | 398 / 402 / 418 |
| middle character | 241 of 418 | 396 / 404 / 418 | 396 / 404 / 418 |
| value replaced by a longer one | 202 of 351 | 255 / 290 / 351 | 237 / 270 / 351 |
| first three characters replaced | 10 of 418 | 336 / 352 / 418 | 336 / 352 / 418 |
| occurrence text deleted, line kept | 8 of 418 | 16 / 218 / 418 | 11 / 138 / 418 |
| whole line deleted | 0 of 413 | 0 / 215 / 413 | 0 / 131 / 413 |

No margin separates a deletion from an edit: a margin of two characters over the next line still
leaves 148 of the 215 sibling lines named for whole-line deletions and costs 50 of the 398
first-character finds. The half floor removes 84 of those 215 and costs 18 of the 255 finds for a
replaced value and none for a single-character change. Summing both runs over the whole line instead
matched within seven cases per row but credits a renamed line with the whole search text.

Method: the replay mutates a scratch export and reads each line with `linereadings.line_runs`;
`scripts/tests/test_linereadings.py` asserts the reading's rules.

**2026-10-10.** The same replay over the eight search texts containing a newline, one bounded
occurrence each, compares the opening run over the whole file they had been read with against the
both-ends reading over windows of the lines each spans. A first character that is a line break is
skipped, and a deletion keeps the occurrence's line breaks. Cells read as in the table above.

| Change to one occurrence | Opening run over the whole file | Both ends over windows |
| --- | --- | --- |
| last character of the value | 7 / 8 / 8 | 5 / 7 / 8 |
| first character of the search text | 0 / 2 / 8 | 5 / 7 / 8 |
| middle character | 6 / 8 / 8 | 5 / 7 / 8 |
| value replaced by a longer one | 7 / 7 / 8 | 6 / 6 / 8 |
| first three characters replaced | 0 / 2 / 8 | 5 / 8 / 8 |
| occurrence text deleted, line breaks kept | 0 / 2 / 8 | 0 / 5 / 8 |

Every edit the windows miss names a sibling holding all but one character of the search text:
`--ubatch-size` beside `--batch-size` in `docker/docker-compose.memory.yml`, and the builder
stage's `FROM` line in `brain/Dockerfile.modelhost`. That is the case the single-line rows show,
a sibling named as the line matching the most of it.
