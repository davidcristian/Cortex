# A measurement run records the card's ceiling by hand

**Status:** done 2026-09-17
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

Every row now prints what it generated, so a stopped row leaves its own token count in the run log.
The other half of a price is the ceiling those tokens were generated under, and that half was taken
by hand: the runbook told an operator to read `enforced.power.limit` against `power.max_limit`
before starting and again while the row served, and nothing failed when they did not. Two runs in a
row were priced with no ceiling recorded beside them.

**What would close it.** The harness already shells out to docker through `_docker`, and its own
`cortex-inj-probe` container runs an image with `nvidia-smi` available, so one `docker exec` reading
`clocks.sm,power.draw,enforced.power.limit,power.max_limit` at the start and end of a row would put
both halves of the price on the same line as the tokens. The reading costs one call per row and
fails nothing on its own, which is the point: a row that prints its ceiling cannot be published
without one.

Two things it deliberately does not do. It does not read the card from inside a test assertion,
since a clock is a property of the run rather than of the behaviour under test. And it does not
refuse a capped card, because a row drawn under a lowered ceiling is still a row as long as the
ceiling is recorded beside its cost.

## History

- 2026-09-13: opened by the run that gave every row a token total and read the card's ceiling at
  idle ([injection-harness-costs](../../readings/injection-harness-costs.md)), and left open here
  with a measurement that raises what it is worth. The card was read twice more the same day with
  nothing running, and the ceiling moved: at 09:38, after a night of unattended work with the
  display asleep, the enforced limit stood under a third of the card's maximum and under three
  fifths of its default, and at 12:53, with the desktop session awake, it stood above nine tenths of
  the maximum and above the default
  ([ADR-0041 decision 20](../../adr/ADR-0041-injection-image-variant.md)). So a row published without a
  ceiling cannot be priced afterwards at all. The second half of the trigger fired: the loads rows
  the runbook publishes for 2026-09-13 have costs with no ceiling beside them.
- 2026-09-17: done. Every row of
  [test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
  now prints a `card reading at start of` and a `card reading at end of` line, the second from a
  `finally` so a stopped row prints it too, and nothing asserts on either. Three things the entry
  had wrong: `_docker` discards what it prints, so the reading makes its own call; the image does
  not include `nvidia-smi`, the container toolkit injects it beside `--gpus all`, so only a card
  row's container has it and a CPU row's line says it is served on the CPU; and a ratio needs
  `clocks.max.sm` beside `clocks.sm`, which is a valid field. The pure half is
  [card_reading.py](../../../brain/packages/inference/tests/card_reading.py) with a CI-side suite,
  seventeen mutants all killed. A real reading through `print_card` was taken against a sleeping
  card container, and six readings over four minutes put the ceiling between 0.80 and 0.88 of the
  card's maximum, which opened
  [R-678](678-a-rows-card-reading-misses-the-ceiling-between-its-ends.md). The other harnesses that
  time the card print no reading, which is
  [R-679](679-a-card-timing-outside-the-injection-harness-carries-no-ceiling.md)
  ([ADR-0041 decision 20](../../adr/ADR-0041-injection-image-variant.md)).
