import os

import pytest
from grpc import aio

from cortex_body_client import GrpcBodyGateway

# Run from inside the brain image against the host body with
# CORTEX_BODY_ENDPOINT=host.docker.internal:50151.
_ENDPOINT = os.environ.get("CORTEX_BODY_ENDPOINT", "127.0.0.1:50151")
_TOKEN = os.environ.get("CORTEX_SEAM_TOKEN", "")


@pytest.mark.integration
async def test_volume_round_trips_against_a_live_body() -> None:
    channel = aio.insecure_channel(_ENDPOINT)
    try:
        gateway = GrpcBodyGateway(channel, token=_TOKEN)
        before = await gateway.get_volume()
        target = 0.2 if before.level > 0.5 else 0.8
        changed = await gateway.set_volume(level=target)
        assert abs(changed.level - target) < 0.05
        restored = await gateway.set_volume(level=before.level, mute=before.muted)
        assert abs(restored.level - before.level) < 0.05
        assert restored.muted is before.muted
    finally:
        await channel.close()
