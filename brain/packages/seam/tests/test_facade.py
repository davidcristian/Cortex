"""Behavior tests for the cortex_seam facade: wire round-trips and a stable export surface."""

import cortex_seam


def test_health_reply_round_trips_on_the_wire() -> None:
    reply = cortex_seam.HealthReply(ready=True, detail="cortex-orchestrator 0.0.0")
    decoded = cortex_seam.HealthReply.FromString(reply.SerializeToString())
    assert decoded == reply
    assert decoded.ready is True
    assert decoded.detail == "cortex-orchestrator 0.0.0"


def test_client_event_oneof_carries_a_user_turn() -> None:
    event = cortex_seam.ClientEvent(
        session_id="session-1",
        user_turn=cortex_seam.UserTurn(text="hello"),
    )
    decoded = cortex_seam.ClientEvent.FromString(event.SerializeToString())
    assert decoded.WhichOneof("event") == "user_turn"
    assert decoded.user_turn.text == "hello"


def test_client_event_oneof_carries_a_cancel() -> None:
    event = cortex_seam.ClientEvent(session_id="session-1", cancel=cortex_seam.Cancel())
    decoded = cortex_seam.ClientEvent.FromString(event.SerializeToString())
    assert decoded.WhichOneof("event") == "cancel"


def test_image_blob_preserves_bytes_and_metadata() -> None:
    blob = cortex_seam.ImageBlob(data=b"\x89PNG", mime_type="image/png", width=8, height=6)
    decoded = cortex_seam.ImageBlob.FromString(blob.SerializeToString())
    assert decoded.data == b"\x89PNG"
    assert decoded.mime_type == "image/png"
    assert (decoded.width, decoded.height) == (8, 6)


def test_every_advertised_name_is_importable() -> None:
    exported = [getattr(cortex_seam, name) for name in cortex_seam.__all__]
    assert all(obj is not None for obj in exported)
    assert sorted(cortex_seam.__all__) == list(cortex_seam.__all__)
