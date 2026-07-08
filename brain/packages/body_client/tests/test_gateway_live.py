"""The GrpcBodyGateway against a live BodyService at CORTEX_BODY_ENDPOINT (ADR-0023).

Integration-marked: excluded from CI and the coverage gate by the workspace addopts
(`-m "not integration"`); run manually against a running body server, e.g. the host-native
Tauri app on Windows or a host-side test server (docs/runbooks/body-volume.md). This proves the
brain→body direction of the seam end to end, covering the reversed seam token, the wire, and the
round-trip, across the container boundary when run from the brain image:

    cd brain && CORTEX_BODY_ENDPOINT=host.docker.internal:50151 \
    CORTEX_SEAM_TOKEN=... uv run pytest -m integration --no-cov packages/body_client

The `--no-cov` matters. The 100% gate in addopts would otherwise fail the run. It reads the
current volume, nudges it, restores it, and toggles mute back to where it started, so it leaves
the host as it found it.
"""

import os

import pytest
from grpc import aio

from cortex_body_client import GrpcBodyGateway

_ENDPOINT = os.environ.get("CORTEX_BODY_ENDPOINT", "127.0.0.1:50151")
_TOKEN = os.environ.get("CORTEX_SEAM_TOKEN", "")


@pytest.mark.integration
async def test_volume_round_trips_against_a_live_body() -> None:
    channel = aio.insecure_channel(_ENDPOINT)
    try:
        gateway = GrpcBodyGateway(channel, token=_TOKEN)
        before = await gateway.get_volume()
        # Nudge the level a little (staying in range), then restore it exactly.
        target = 0.2 if before.level > 0.5 else 0.8
        changed = await gateway.set_volume(level=target)
        assert abs(changed.level - target) < 0.05
        restored = await gateway.set_volume(level=before.level, mute=before.muted)
        assert abs(restored.level - before.level) < 0.05
        assert restored.muted is before.muted
    finally:
        await channel.close()
