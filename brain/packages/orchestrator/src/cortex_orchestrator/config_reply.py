"""How far a user's own reply may go before the model must answer (ADR-0005 capped-reply
addendum).

Its own module for the reason ``config_tools.py`` and ``config_subagents.py`` are: ``config.py``
sits at its line cap, and these two knobs are one decision with one paragraph of argument rather
than two loose fields. They are the deployment's producer of ``GenerationBounds`` on the two
paths a user reads, the cortex turn and the deep phase that continues it; the delegated path has
its own pair in ``config_subagents.py``, deliberately separate because a subtask nobody reads and
an answer somebody is watching are not bounded on the same argument.

Both defaults are today's request, byte for byte: no cap and whatever the tier's chat template
does about thinking. So a deployment that sets neither sends what this repo has always sent, and
the whole module reduces to ``None``.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import GenerationBounds

__all__ = ["ReplyBoundsConfig"]


class ReplyBoundsConfig(BaseSettings):
    """Env-only bounds for a user-facing reply, read once at the composition root."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_REPLY_")

    # env CORTEX_REPLY_MAX_TOKENS caps how far each completion of a user's turn may decode. 0,
    # NOTE on the pairing below: what a cap must be paired with is a BOUNDED TRACE, and turning
    # thinking off is only the cheapest way to bound one. A tier started with llama.cpp's own
    # ``--reasoning-budget N`` (CORTEX_REASONING_BUDGET, ADR-0005 trace-budget addendum) leaves the
    # cap room to answer in with deliberation still on: measured on the shipped cortex, 512 tokens
    # against an unbounded trace returned an EMPTY reply 3 of 3 and the same 512 under a budget of
    # 128 returned 1488 and 1561 characters of answer.
    # the default, sends no cap at all and leaves the real bound where it has always been, the
    # server's context window. Measured on the shipped cortex, an ordinary open question decodes
    # 1715 to 1941 tokens in 32.5 s to 37.5 s, so a cap meant to shorten a wait rather than to
    # truncate an answer sits above that, and it is the deployment that knows which of its own
    # questions are long. Whatever cuts a reply, this cap or the context window, the turn now says
    # so under the text (``REPLY_CAPPED_NOTE``), which is what makes setting it safe.
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

    def bounds(self) -> GenerationBounds | None:
        """The port's value for this deployment, or ``None`` when it asked for neither knob.

        ``None`` rather than an all-default ``GenerationBounds`` so the unbounded deployment
        takes the same path a caller that passes nothing takes, which is the one the adapter
        renders as the original request.
        """
        if not self.max_tokens and self.thinking:
            return None
        return GenerationBounds(max_tokens=self.max_tokens or None, thinking=self.thinking)
