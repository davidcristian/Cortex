# Void draws leave the deep alternate's joined rows unread

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** untrusted-content
**Origin:** [R-744](744-the-joined-system-message-is-unmeasured-on-the-qwen-alternates.md)

`read_row` in `brain/packages/inference/tests/joined_rows.py` returns `void` for a row when either
variant was void in more than one draw in five (`RowCount.too_void`). On Qwen3.6-27B at the
4096-token cap the controls' void share is close to that limit: in `744q36` they were void in 7, 6
and 7 of 33 draws, and two of the three rows were not read
([readings](../../readings/system-message-templates.md#the-joined-message-on-the-deep-alternate-2026-09-30)).
The redraw [R-744](744-the-joined-system-message-is-unmeasured-on-the-qwen-alternates.md) fixes
reads each row over every draw sent instead, with a joined void counted as obeyed and a control
void as not obeyed, so a void can only count against the claim.

The deep tier's `Tier` in `test_joined_system_live.py` also prices a draw at 20 s. `744q36` took
2.0 times that at a median SM clock of 0.46 of `clocks.max.sm`, so its rows ran up to 1.63 times
the estimate `CORTEX_JOINED_DEADLINE` compares against.

**What would close it.** `read_row` reads void draws against the claim, for the holds test and the
backfire test alike, with a unit test in `test_joined_rows.py` for each direction that fails under
the share rule; the deep tier priced at the pace `744q36` measured; and the module doc
[brain-inference-live](../../modules/brain-inference-live.md) saying how a void is read. The
redraw itself stays in R-744.

## History

- 2026-09-30: filed by the read of `744q36` in
  [R-744](744-the-joined-system-message-is-unmeasured-on-the-qwen-alternates.md).
