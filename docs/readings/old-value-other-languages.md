# Readings: the old value note on a statement in another language

What a stated new value of a fact in French, German, Spanish or Romanian names as the old value,
on the reader before and after `FACT_VALUES_OTHER` (`fact_statement.py`). The rule the reader
follows is in the [memory module doc](../modules/brain-core-memory.md); this record holds the
replay it was checked on.

## Method

Taken 2026-11-25 with no model: `hold_old_value` (`memory_old_value.py`) on each message beside
one row in the in-memory store, the reply `Got it.`, on a `git archive` copy of the core before
the change and on the tree after it. Scripts in `~/.cache/cortex-run/2026-11-25/s2/replay/`
(`corpus2.py` builds the pairs, `replay.py` runs one reader, `diff.py` compares two).

- **Same text rows.** 8,068 messages: every string literal of the brain tests and every
  backticked text in `docs/readings/` that holds a digit and fits on one line in under 300
  characters, plus 40 hand written statements, five in each of French, German, Spanish,
  Romanian, Italian, Portuguese, Dutch and Polish. Each message stands beside one row, the same
  text with every run of digits set to `90909`.
- **Cross pairs.** The 97 messages that name a value after the change or are hand written, each
  beside the rows of the other 96: 9,296 pairs.

## Results

| Pairs | Notes before | Notes after | Unchanged | New | Lost or changed |
| --- | --- | --- | --- | --- | --- |
| Same text rows | 149 | 225 | 149 | 76 | 0 |
| Cross pairs | 0 | 135 | 0 | 135 | 0 |

- Every English note is unchanged. Each of the 76 new notes is a French, German, Spanish or
  Romanian statement, alone or after a request to remember, beside its own fact with another
  value.
- Hand written statements that name the old value: French 5 of 5, German 4 of 5 (`Mein
  Geburtstag ist 12. Mai.` reads as two sentences), Spanish 5 of 5, Romanian 5 of 5, and
  Italian, Portuguese, Dutch and Polish 0 of 20.
- Each of the 135 cross pair notes stands beside a row with the same fact words, possessive and
  language: a bare statement beside a request to remember the same fact, or the two German
  orders (`Mein Alarmcode ist 5528.` beside `Merk dir, dass mein Alarmcode 90909 ist.`). None
  stands beside another fact (`mon code est 5528` beside `Mon code d'alarme est 90909.`),
  another possessive or a row in another language.
- The five messages the task named, each beside a row of the same fact with `4826` in the same
  language, now name `4826`; `test_memory_old_fact_other.py` holds them with the near misses.
