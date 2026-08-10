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


def test_an_unset_capture_target_is_the_whole_display() -> None:
    # Zero is DISPLAY, which is what makes the new field safe in both directions: a brain that
    # names no target asks for exactly the behaviour this seam has always had, and a body that
    # does not know the field reads the same zero.
    assert cortex_seam.CaptureTarget.CAPTURE_TARGET_DISPLAY == 0
    assert cortex_seam.CaptureTarget.CAPTURE_TARGET_FOCUS == 1
    request = cortex_seam.CaptureScreenRequest(max_edge=2048)
    decoded = cortex_seam.CaptureScreenRequest.FromString(request.SerializeToString())
    assert decoded.target == cortex_seam.CaptureTarget.CAPTURE_TARGET_DISPLAY
    assert decoded.max_edge == 2048


def test_a_reply_that_names_no_target_reads_as_the_whole_display() -> None:
    # The same zero on the other direction, and the reason the reply field is safe to add: a
    # body predating it can only have taken a whole-display picture, so the default is a
    # reading rather than a guess.
    reply = cortex_seam.CaptureScreenReply(image=cortex_seam.ImageBlob(width=4, height=4))
    decoded = cortex_seam.CaptureScreenReply.FromString(reply.SerializeToString())
    assert decoded.resolved_target == cortex_seam.CaptureTarget.CAPTURE_TARGET_DISPLAY


def test_a_resolved_capture_target_round_trips_on_the_wire() -> None:
    reply = cortex_seam.CaptureScreenReply(
        image=cortex_seam.ImageBlob(width=4, height=4),
        resolved_target=cortex_seam.CaptureTarget.CAPTURE_TARGET_FOCUS,
    )
    decoded = cortex_seam.CaptureScreenReply.FromString(reply.SerializeToString())
    assert decoded == reply
    assert decoded.resolved_target == cortex_seam.CaptureTarget.CAPTURE_TARGET_FOCUS


def test_a_capture_target_round_trips_on_the_wire() -> None:
    request = cortex_seam.CaptureScreenRequest(
        max_edge=2048, target=cortex_seam.CaptureTarget.CAPTURE_TARGET_FOCUS
    )
    decoded = cortex_seam.CaptureScreenRequest.FromString(request.SerializeToString())
    assert decoded == request
    assert decoded.target == cortex_seam.CaptureTarget.CAPTURE_TARGET_FOCUS


def test_session_summary_round_trips_on_the_wire() -> None:
    summary = cortex_seam.SessionSummary(
        session_id="s-1", title="about cats", preview="cats are great", last_activity_unix_ms=1234
    )
    decoded = cortex_seam.SessionSummary.FromString(summary.SerializeToString())
    assert decoded == summary
    assert decoded.session_id == "s-1"
    assert decoded.last_activity_unix_ms == 1234


def test_session_message_round_trips_on_the_wire() -> None:
    message = cortex_seam.SessionMessage(
        role="assistant", text="hello", turn_id="t-1", at_unix_ms=99
    )
    reply = cortex_seam.GetSessionMessagesReply(messages=[message])
    decoded = cortex_seam.GetSessionMessagesReply.FromString(reply.SerializeToString())
    assert list(decoded.messages) == [message]
    assert decoded.messages[0].role == "assistant"


def test_every_advertised_name_is_importable() -> None:
    exported = [getattr(cortex_seam, name) for name in cortex_seam.__all__]
    assert all(obj is not None for obj in exported)
    # A stable export surface: no duplicates. Ordering is owned by ruff's RUF022 (which groups
    # SCREAMING_CASE constants like SEAM_TOKEN_HEADER ahead of the class re-exports), not a plain
    # `sorted()`. The two diverge once __all__ carries a constant.
    assert len(set(cortex_seam.__all__)) == len(cortex_seam.__all__)
