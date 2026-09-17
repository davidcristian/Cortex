# Readings: every check proved able to fail

Each table below is one check broken on purpose and the tests that failed for it. The rule these
answer is in the working agreement of [AGENTS.md](../../AGENTS.md): a check that cannot fail is a
defect, so a new check is broken before it is trusted. A row naming no failure is a hole in the
suite and says so.

## The prose check and its three readers

Over `scripts/tests/test_prosecheck.py`, `test_bannedwords.py`, `test_commentblocks.py` and
`test_slashcomments.py`, 135 tests, all passing before each edit.

```
file              mutation                                    failed
bannedwords.py    a match on the next line also counted here     2
bannedwords.py    case-sensitive matching                        1
bannedwords.py    code spans not masked                          3
bannedwords.py    no word boundary before a match                1
bannedwords.py    phrase words joined by one space only          2
bannedwords.py    separator row read as words                    5
commentblocks.py  a blank line ends a block                      1
commentblocks.py  a code line does not end a block               2
commentblocks.py  directives count toward a block                2
commentblocks.py  docstring counts blank lines                   4
commentblocks.py  docstring sliced by characters, not bytes      1
commentblocks.py  shebang allowed on any line                    1
prosecheck.py     _generated not skipped                         1
prosecheck.py     exactly three lines reported                   1
prosecheck.py     fenced markdown searched                       1
prosecheck.py     git-ignored files walked                       1
prosecheck.py     limit raised to four lines                     4
prosecheck.py     problems exit 0                                2
prosecheck.py     table rows not exempt                          2
slashcomments.py  Rust block comments do not nest                1
slashcomments.py  char literals read as lifetimes                1
slashcomments.py  escapes in strings ignored                     2
slashcomments.py  leading * of a block line kept                 1
slashcomments.py  multi-line block comment lines stay code       1
slashcomments.py  no regex literals                              1
slashcomments.py  template expressions not lexed                 1
```

## The banned word in a commit message

Over `scripts/tests/test_commitlint.py`, 96 tests.

```
mutation                               failed
a paste is searched too                1
an unreadable table passes             1
every line read as one run             1
the word check is never called         1
```

## The commit body word count

Over the 102 tests of `scripts/tests/test_commitlint.py`.

```
mutation                          | result
the cap is one word too loose     | 2 failed
a paste counts toward the cap     | 2 failed
the subject counts toward the cap | 3 failed
an over-long body is not reported | 2 failed
```

## The exemption list in the prose check

Over the 2096 tests of the `scripts/` suite.

```
mutation                                             | result
a missing exemption file is skipped                  | 1 failed
a missing exemption target is skipped                | 2 failed
a long docstring is reported although it is exempt   | 2 failed
exempt lines are still searched for banned words     | 5 failed
a file's exemption is never looked up                | 2 failed
a decorator name is read as its last part only       | 3 failed
every function is read as decorated                  | 2 failed
the module docstring is the first docstring anywhere | 1 failed
```

## The line cap over decision and readings records

Failing tests in `scripts/tests/test_linecap.py`, 56 tests, per mutation.

```
record cap default 250 raised to 251                1 of 56
records held to the source cap                      5 of 56
over-cap test > weakened to >=                      5 of 56
records dropped from the walk                       7 of 56
a README counted as a record                        3 of 56
any .md in docs/adr counted as a record             2 of 56
a record matched by name at any depth               1 of 56
docs/readings dropped from the rule                 3 of 56
the record floor removed                            3 of 56
a record counted in the source tally                5 of 56
a violation printed with the source cap             2 of 56
the record summary printed with the source cap      1 of 56
--record-max-lines ignored                          1 of 56
unmutated                                           0 of 56
```

## The line cap over every markdown file

Over the 58 tests of `scripts/tests/test_linecap.py`.

```
mutation                                                 | result
markdown is not capped at all                            | 15 failed
an exempt index is capped and counted like the rest      |  2 failed
the document cap is one line too loose                   | 11 failed
an exemption naming a missing file is taken as generated |  1 failed
an exemption is kept once the file is not generated      |  1 failed
a tree with no markdown file passes                      |  3 failed
```

## The backlog's own words

Over `scripts/backlogcheck.py`, one task file edited per row.

```
mutation                     result
status `landed <date>`       caught, unknown status
state `fix when it bites`    caught, unknown open state
state `standing: <why>`      caught, unknown status
field `**Sitting:**`         caught, missing field Session
heading `## Trail`           not caught
```
