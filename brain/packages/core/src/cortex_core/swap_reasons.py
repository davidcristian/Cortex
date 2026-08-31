"""What a ``FAILED`` handoff record says about itself."""

DRAIN_TIMEOUT_REASON = (
    "delegated work was still running when the drain bound elapsed, so the handoff was aborted "
    "before anything was evicted"
)

TORN_DOWN_REASON = "the turn was torn down before the handoff finished"

STRANDED_REASON = "the brain restarted while this handoff was still in flight"
