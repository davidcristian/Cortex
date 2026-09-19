# The other lineup rows have no obeyed count beside their mention count

**Status:** done 2026-09-06
**Area:** inference
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

The 2026-09-05 repeat published an obeyed count beside a mention count for four card rows: the
subagent pick on `shipped-argv` and on `budget-alone`, the cortex pick, and the brain pick. Every
other text row this repo publishes still has a mention count alone, with no reply kept behind it:
the four other subagent candidates on `shipped-argv` and `request-key` in the 2026-09-04 switch rows
and the lineup table, the cortex alt in the lineup table, the pick's `request-key` repeat, the
pick's CPU row from 2026-09-05, and the three deep candidates that were never drawn at all. One
session per row would say whether those counts were tokens written or instructions reported. On the
three rows drawn again that night the answer was tokens written every time, but that is three rows
on two models of one family, and the entries the vision readings recorded describing were all on the
other channel.

Closing it means running `-k "shipped-argv and gpu and not E4B and not 12B"` once, which is the four
other subagent candidates and the cortex alt in one session, and publishing the obeyed count beside
each mention count. Add every fired reply to `RECORDED` in
[test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py) with the
reading given by hand.

## History

- 2026-09-05: opened by the close of
  [R-563](563-the-text-arms-published-matrices-are-mention-counts-with-no-reply-behind-them.md),
  whose repeat named which rows it drew and which it did not.
- 2026-09-06: done. The session drew four of its five rows and published an obeyed count beside
  every mention count in the 2026-09-04 switch table and the lineup table
  ([injection text rows](../../readings/injection-text-rows.md)), and all fourteen fired replies are
  in `RECORDED` with the reading a hand sort gives them, which the structural reading agrees with on
  every one. Every mention count reproduced what was published, and the two readings differed on
  Qwen3.5-4B framed, 2 mentioned against 0 obeyed, so the entry's expectation that they would agree
  cell for cell is wrong. The fifth row, the cortex alt, cannot run on this host: its artifact is
  not on the mount and the server's load error reaches the harness as a health timeout
  ([R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md)).
  The `request-key` repeats and the CPU row stay where the entry left them.
