"""Whether the cortex can call the host body over ``BodyService``, and how long it may wait.

Its own module for the reason ``config_tools.py``, ``config_subagents.py``, ``config_reply.py``
and ``config_schedule.py`` are: ``config.py`` sits at its line cap, and the body's knobs are one
decision with several paragraphs of argument rather than a handful of loose fields.

The two deadline defaults are **imported, not restated**. ``cortex_body_client`` owns the calls,
so it owns how long they may take; a settings module that spelled its own ``5.0`` would be a
second default that only looks like the first. This is the same move ``config.py`` makes with the
session adapter's ``DEFAULT_REDIS_URL``.
"""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_body_client import DEFAULT_CALL_TIMEOUT_S, DEFAULT_CAPTURE_TIMEOUT_S
from cortex_core import MAX_IMAGE_BYTES, MAX_IMAGE_EDGE

BodyBackendName = Literal["none", "grpc"]

# The edge the brain asks for when nothing overrides it, named rather than spelled inside the
# ``Field(...)`` below because it is not only ours: the compose stack ships it as a substitution
# default and the vision runbook quotes it as the number a deployment is running, so
# `scripts/crosscheck.py` ties those to this. The two deadline defaults need no such hoist,
# arriving already named from the client that owns the calls.
DEFAULT_CAPTURE_MAX_EDGE = 2048


class BodyConfig(BaseSettings):
    """Whether the cortex can call the host body over ``BodyService`` (ADR-0023).

    ``none`` (the default) disables the brain→body direction. CI and the no-body dev loop
    run without it, and the volume tools are simply not registered. ``grpc`` enables it and
    requires ``endpoint`` (``host:port`` of the host-native body's ``BodyService`` server; from
    the dockerized brain this is ``host.docker.internal:<port>``). The seam token is the shared
    ``CORTEX_SEAM_TOKEN`` (ADR-0016), attached by the client, so it lives in ``SeamServerConfig``
    and is not duplicated here.

    Two capture bounds ride with a request (ADR-0029). ``capture_max_edge`` and
    ``max_image_bytes`` are what the brain asks the body for and, more importantly, what it holds
    the reply to: the body clamps both and an older body ignores both, so they are re-verified on
    receipt. ``max_image_bytes`` defaults to the same 6 MiB as the body's own ceiling, which is
    the point of sending it rather than trusting two constants to stay equal.

    ``capture_max_edge`` defaults to **2048 rather than to the body's own 1600**, which is the
    brain half of the measured legibility pair (ADR-0029's legibility addendum): with the model
    host's ``CORTEX_IMAGE_MAX_TOKENS`` at 1024, a 4K desktop goes from 6 to 8 of 47 ground-truth
    strings read to 36 to 38. It belongs on this side because the number that makes it worth
    paying for is the model's per-image token budget, which the body cannot know; a body asked
    for nothing keeps answering at its own conservative 1600, where a worst-case incompressible
    screen still encodes inside the byte ceiling. ``0`` still means "the body's own default", so
    a deployment can hand the choice back.

    **Two deadlines, because the calls differ** (ADR-0029's uniform-deadline addendum).
    ``capture_timeout_s`` bounds a capture, which is legitimately slow. ``call_timeout_s`` bounds
    every other call on this seam, which is fast when it works and unbounded when it does not:
    the body runs each handler on ``spawn_blocking`` because Core Audio and the toast manager are
    COM, and a COM call can park its thread for as long as the host takes. Nothing above the
    gateway bounds a tool call, so without this one a wedged audio endpoint hangs the turn.
    Folding both onto one number would either starve a capture or hand a volume read ten seconds
    of patience it can never spend.

    All four are **bounded here so a misconfiguration fails at boot**, the way the model host's
    ports and context sizes do. Both capture bounds ride uint32 proto fields, so a negative or
    over-wide value is a request that cannot be built at all, and unbounded they turned every
    capture of that deployment into a turn-killing exception rather than a startup refusal.
    ``max_image_bytes`` may only tighten the domain ceiling (the body clamps to its own anyway,
    so a looser number is a bound nothing would honour), and ``capture_max_edge`` may not exceed
    the largest edge an ``ImagePart`` would accept, which the reply is checked against too. A
    deadline is positive because a zero or negative one is a call that can never succeed.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_BODY_")

    backend: BodyBackendName = "none"
    endpoint: str = ""
    capture_max_edge: int = Field(default=DEFAULT_CAPTURE_MAX_EDGE, ge=0, le=MAX_IMAGE_EDGE)
    max_image_bytes: int = Field(default=MAX_IMAGE_BYTES, gt=0, le=MAX_IMAGE_BYTES)
    capture_timeout_s: float = Field(default=DEFAULT_CAPTURE_TIMEOUT_S, gt=0)
    call_timeout_s: float = Field(default=DEFAULT_CALL_TIMEOUT_S, gt=0)

    @model_validator(mode="after")
    def _grpc_needs_an_endpoint(self) -> "BodyConfig":
        if self.backend == "grpc" and not self.endpoint:
            msg = "CORTEX_BODY_ENDPOINT is required when CORTEX_BODY_BACKEND=grpc"
            raise ValueError(msg)
        return self
