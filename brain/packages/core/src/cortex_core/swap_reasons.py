"""What a ``FAILED`` handoff record says about itself (ADR-0030 failed-reason addendum)."""

# The straggler abort: the drain bound elapsed with delegated work still in flight, so v1 killed
# nothing and evicted nothing. Names the bound rather than the tenant, since which subagent was
# still running is the scheduler's to say and is not knowable from here.
DRAIN_TIMEOUT_REASON = (
    "delegated work was still running when the drain bound elapsed, so the handoff was aborted "
    "before anything was evicted"
)

# Cancellation and stream teardown. The record is settled on the way out so a live one cannot
# strand the next boot, and this is what that write is able to say: not that anything broke, but
# that nothing was left running this sequence.
TORN_DOWN_REASON = "the turn was torn down before the handoff finished"

# Boot recovery's verdict on a record its own process did not write. A handoff cannot outlive
# the process running it, so a non-terminal record found at startup is one a crash interrupted,
# and this says that rather than leaving the state to be read as a diagnosis.
STRANDED_REASON = "the brain restarted while this handoff was still in flight"
