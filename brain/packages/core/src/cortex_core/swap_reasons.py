"""What a ``FAILED`` handoff record says about itself (ADR-0030 failed-reason addendum).

The companion of ``swap_notes.py`` and its deliberate opposite. A note is what the **user** is
told, and it describes the GPU rather than the fault, because the person waiting on a turn is
owed what is true of their machine now. A reason is what the **record** keeps, and it describes
the fault, because the reader of a settled record is whoever is asking why a handoff that is
already over did not happen. The two never share a string: a note that drifted into naming a
model host route would be the wrong sentence in a reply, and a reason that softened into a note
would be the wrong sentence in a diagnosis.

Three of the five ways a handoff ends failed are app-authored and live here, being facts about
the sequence rather than about anything that raised. The other two carry the message of the
error itself (``ModelManagerError`` from the swap, ``InferenceError`` from the deep model's own
server), which is the whole point of the field: on the swap path that message is built out of
the model host's status code and the leading characters of its response body, so this is where
the daemon's own words reach the brain's side and stay there.

All of it is app-authored or error text, never model text, so none of it needs a guardrail pass
and none of it can be steered by whatever the cortex read before it escalated.
"""

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
