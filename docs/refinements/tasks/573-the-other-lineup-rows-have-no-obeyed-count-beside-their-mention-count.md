# The other lineup rows have no obeyed count beside their mention count

**Status:** landed 2026-09-06
**Area:** inference
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Opened 2026-09-05 by the close of
[R-563](563-the-text-arms-published-matrices-are-mention-counts-with-no-reply-behind-them.md),
which drew one model per tier again under both readings and marked every published text table as
a mention count where it stands.

The re-drawn-rows addendum at ADR-0013 publishes an obeyed count beside a mention count for four
card rows: the subagent pick on `shipped-argv` and on `budget-alone`, the cortex pick, and the
brain pick. Every other text row this repo publishes still has a mention count alone, with no reply
kept behind it: the four other subagent candidates on `shipped-argv` and `request-key` in
[ADR-0004](../../adr/ADR-0004-model-lineup.md)'s switch-row addendum and lineup table, the cortex
alt in the lineup table, the pick's `request-key` replicate, the pick's CPU row in the
placement-row addendum, and the three deep candidates that were never drawn at all. What one
sitting per row would say is whether those counts were tokens written or instructions reported.
On the three rows drawn again tonight the answer was tokens written every time, so the mention
count and the obeyed count agreed cell for cell, but that is three rows on two models of one
family, and the entries the readings addendum recorded describing were all on the other channel.

**Why it was left.** The close was scoped to one model per tier on the card, about a minute per
row, and the rows above are a different scale: four subagent candidates on two switches is eight
card rows, the cortex alt is a two-minute row, and the pick's CPU row is half an hour. Nothing
published rests on the other candidates' obeyed count, since the pick and the cortex are what
ship.

**What would close it.** Run `-k "shipped-argv and gpu and not E4B and not 12B"` once, which is
the four other subagent candidates and the cortex alt in one sitting, and publish the obeyed count
beside each mention count in the switch-row addendum and the lineup table. Add every fired reply
to `RECORDED` in
[test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py) with the
verdict it was given by hand. The `request-key` replicates and the CPU row can wait for the
sittings that already owe them, since a route or a placement is not where a reading changes.

## Trail

- 2026-09-05: opened by the close of
  [R-563](563-the-text-arms-published-matrices-are-mention-counts-with-no-reply-behind-them.md),
  whose re-drawn-rows addendum at ADR-0013 names which rows it drew and which it did not.
- 2026-09-06: landed. The sitting drew four of its five rows and published an obeyed count beside
  every mention count in the switch-row addendum's table and the lineup table (the
  [ADR-0004 lineup-readings addendum](../../adr/ADR-0004-model-lineup.md)), and all fourteen fired
  replies are in `RECORDED` with the verdict a hand sort gives them, which the structural reading
  agrees with on every one. Every mention count reproduced what was published, and the two readings
  parted on Qwen3.5-4B's framed arm, 2 mentioned against 0 obeyed, so the entry's expectation that
  the counts would agree cell for cell as they had on the card rows is falsified. The fifth row,
  the cortex alt, cannot draw on this host: its artifact is not on the mount and the server's load
  error reaches the harness as a health timeout
  ([R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md)).
  The `request-key` replicates and the CPU row stay where the entry left them.
