"""How far a user's own reply may go before the model must answer (ADR-0005 capped-reply
addendum).

Its own module for the reason ``config_tools.py`` and ``config_subagents.py`` are: ``config.py``
sits at its line cap, and these knobs are one decision with one paragraph of argument rather
than three loose fields. They are the deployment's producer of ``GenerationBounds`` on the two
paths a user reads, the cortex turn and the deep phase that continues it; the delegated path has
its own pair in ``config_subagents.py``, deliberately separate because a subtask nobody reads and
an answer somebody is watching are not bounded on the same argument.

Every default is today's request, byte for byte: no cap, whatever the tier's chat template does
about thinking, and whatever budget the tier was started with. So a deployment that sets none of
them sends what this repo has always sent, and the whole module reduces to ``None``.

This is the one producer of a trace budget in the repo that ships unset, and that is a decision
rather than an omission (ADR-0005 request-lever addendum). The three side calls whose deliberation
is thrown away unread name a zero, because nobody loses anything they were reading; here the trace
is what a user reads while the reply is written, so the count is the deployment's to name and
nothing derives one from the thinking switch.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import GenerationBounds

__all__ = ["ReplyBoundsConfig"]

# What ``CORTEX_REPLY_TRACE_TOKENS`` says when the deployment has not set it: leave the trace to
# whatever the tier was started with. It cannot be the falsy value, for the reason the model host's
# own sentinel cannot: ``0`` is a real setting here, meaning the trace ends at once, so folding it
# into "nobody asked" would cost a deployment the knob it chose. It is deliberately a separate
# constant from that sidecar's ``-1`` rather than a shared one, the two being an env field's
# "unset" and llama.cpp's own value for unrestricted, free to move apart.
_TRACE_FROM_TIER = -1


class ReplyBoundsConfig(BaseSettings):
    """Env-only bounds for a user-facing reply, read once at the composition root."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_REPLY_")

    # env CORTEX_REPLY_MAX_TOKENS caps how far each completion of a user's turn may decode. 0, the
    # default, sends no cap at all and leaves the real bound where it has always been, the server's
    # context window. Measured on the shipped cortex, an ordinary open question decodes 1715 to
    # 1941 tokens in 32.5 s to 37.5 s, so a cap meant to shorten a wait rather than to truncate an
    # answer sits above that, and it is the deployment that knows which of its own questions are
    # long. Whatever cuts a reply, this cap or the context window, the turn says so under the text
    # (``REPLY_CAPPED_NOTE``), which is what makes setting it safe.
    #
    # A cap has to be paired with a bounded trace, and turning thinking off is only the cheapest
    # way to bound one. A tier started with llama.cpp's own ``--reasoning-budget N``
    # (CORTEX_REASONING_BUDGET, ADR-0005 trace-budget addendum) leaves the cap room to answer in
    # with deliberation still on: measured on the shipped cortex, 512 tokens against an unbounded
    # trace returned an empty reply 3 of 3, and the same 512 under a budget of 128 returned 1488
    # and 1561 characters of answer.
    max_tokens: int = Field(default=0, ge=0)
    # env CORTEX_REPLY_THINKING keeps the model's deliberation on, which is the default and what
    # every deployment has had. False asks the chat template to skip it, which is the lever for
    # the wait rather than for the length: measured on the shipped cortex the whole of 11.8 s to
    # 15.0 s before the first word is the trace, 2545 to 3064 characters of it, against about
    # 1.2 s with thinking off. The cost is the answer's quality on exactly the questions worth
    # waiting for, and on the deep tier it is the tier's whole reason for existing, the pick
    # having been chosen over faster artifacts for reaching an answer inside its trace at all
    # (ADR-0004). It also empties the thinking status the overlay renders, there being no trace
    # to show.
    thinking: bool = True
    # env CORTEX_REPLY_TRACE_TOKENS is how far a user's reply may deliberate before the engine ends
    # the trace and starts the answer (ADR-0005 request-lever addendum). Unset by default, which
    # leaves the count where it has always been, on the tier's own --reasoning-budget, so a
    # deployment that names nothing sends the request it always sent. It sits between the two knobs
    # above: they decide whether the model deliberates at all, and this bounds how long a trace
    # that does happen may be, which is what a deployment reaches for when it wants the wait
    # shorter without giving the answer up. Measured on the shipped cortex, an unrestricted trace
    # spends 2323 to 2996 characters and 10.1 to 12.6 s before the first word, 128 spends 483 to
    # 536 and 1.7 to 2.6 s, and the reply is the same size in both.
    #
    # It is deliberately not derived from `thinking`, which is why it is a separate field rather
    # than a zero the adapter could infer. A user's reply renders its trace as the thinking status
    # the overlay shows (ADR-0020), so a deployment that turned the switch off on a tier that
    # ignores it is looking at the evidence that it did; making the switch also spend a zero here
    # would blank that surface with nothing reporting it, and this is the one place in this repo
    # where a bounded trace is a loss rather than a saving.
    trace_tokens: int = Field(default=_TRACE_FROM_TIER, ge=_TRACE_FROM_TIER)

    def bounds(self) -> GenerationBounds | None:
        """The port's value for this deployment, or ``None`` when it asked for none of the knobs.

        ``None`` rather than an all-default ``GenerationBounds`` so the unbounded deployment
        takes the same path a caller that passes nothing takes, which is the one the adapter
        renders as the original request.
        """
        traced = self.trace_tokens != _TRACE_FROM_TIER
        if not self.max_tokens and self.thinking and not traced:
            return None
        return GenerationBounds(
            max_tokens=self.max_tokens or None,
            thinking=self.thinking,
            trace_tokens=self.trace_tokens if traced else None,
        )
