"""How far a user's own reply may go before the model must answer."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import GenerationBounds

__all__ = ["ReplyBoundsConfig"]

# What ``CORTEX_REPLY_TRACE_TOKENS`` says when the deployment has not set it: leave the trace to
# whatever the tier was started with. It cannot be 0, which is a real setting here meaning the
# trace ends at once.
_TRACE_FROM_TIER = -1


class ReplyBoundsConfig(BaseSettings):
    """Env-only bounds for a user-facing reply, read once at the composition root."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_REPLY_")

    # 0 sends no cap at all and leaves the real bound at the server's context window. A cap has
    # to be paired with a bounded trace: measured on the shipped cortex, 512 tokens against an
    # unbounded trace returned an empty reply 3 times of 3.
    max_tokens: int = Field(default=0, ge=0)
    thinking: bool = True
    trace_tokens: int = Field(default=_TRACE_FROM_TIER, ge=_TRACE_FROM_TIER)

    def bounds(self) -> GenerationBounds | None:
        """The port's value for this deployment, or ``None`` when it set none of the three."""
        traced = self.trace_tokens != _TRACE_FROM_TIER
        if not self.max_tokens and self.thinking and not traced:
            return None
        return GenerationBounds(
            max_tokens=self.max_tokens or None,
            thinking=self.thinking,
            trace_tokens=self.trace_tokens if traced else None,
        )
