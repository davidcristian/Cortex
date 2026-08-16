"""How far a user's own reply may go before the model must answer (ADR-0005 capped-reply
addendum).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import GenerationBounds

__all__ = ["ReplyBoundsConfig"]


class ReplyBoundsConfig(BaseSettings):
    """Env-only bounds for a user-facing reply, read once at the composition root."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_REPLY_")

    max_tokens: int = Field(default=0, ge=0)
    thinking: bool = True

    def bounds(self) -> GenerationBounds | None:
        """The port's value for this deployment, or ``None`` when it asked for neither knob."""
        if not self.max_tokens and self.thinking:
            return None
        return GenerationBounds(max_tokens=self.max_tokens or None, thinking=self.thinking)
