from collections.abc import AsyncGenerator, AsyncIterator
from typing import cast

import pytest
from grpc import aio

from cortex_core import (
    MAX_IMAGE_BYTES,
    AttachmentError,
    EchoInferenceBackend,
    ImagePart,
    InMemorySessionStore,
    SystemClock,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
)
from cortex_orchestrator import (
    ERROR_CODE_ATTACHMENT_REFUSED,
    RpcServerConfig,
    converse,
    create_server,
    read_attachments,
)
from cortex_seam import BrainServiceStub, ClientEvent, ImageBlob, ServerEvent, UserTurn

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _blob(data: bytes = _PNG, mime_type: str = "image/png") -> ImageBlob:
    return ImageBlob(data=data, mime_type=mime_type, width=640, height=480)


def _turn(*blobs: ImageBlob) -> ClientEvent:
    return ClientEvent(session_id="s", user_turn=UserTurn(text="what is this?", images=blobs))


async def _events_from(*events: ClientEvent) -> AsyncIterator[ClientEvent]:
    for event in events:
        yield event


class _RecordingTurn:
    def __init__(self) -> None:
        self.images: list[tuple[ImagePart, ...]] = []

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str, images: tuple[ImagePart, ...] = ()
    ) -> AsyncGenerator[TurnEvent, None]:
        del session_id, text
        self.images.append(images)
        yield TurnCompleted(turn_id=turn_id, full_text="")


def test_a_well_formed_blob_becomes_an_image_part() -> None:
    assert read_attachments([_blob()]) == (
        ImagePart(data=_PNG, mime_type="image/png", width=640, height=480),
    )


def test_a_blob_the_image_part_refuses_is_named_by_its_position() -> None:
    with pytest.raises(AttachmentError, match="attachment 2 was refused: unsupported image type"):
        read_attachments([_blob(), _blob(mime_type="image/gif")])


def test_a_blob_whose_bytes_are_not_its_type_is_refused() -> None:
    with pytest.raises(AttachmentError, match="attachment 1 is declared image/jpeg"):
        read_attachments([_blob(mime_type="image/jpeg")])


async def test_a_refused_attachment_ends_the_stream_before_any_turn_runs() -> None:
    runner = _RecordingTurn()
    stream = converse(lambda _c, _p: runner, _events_from(_turn(_blob(mime_type="image/gif"))))
    events = [event async for event in stream]
    assert [event.WhichOneof("event") for event in events] == ["error"]
    assert events[0].error.code == ERROR_CODE_ATTACHMENT_REFUSED
    assert "unsupported image type 'image/gif'" in events[0].error.message
    assert runner.images == []


async def test_the_attached_images_reach_the_turn_and_a_bare_turn_has_none() -> None:
    runner = _RecordingTurn()
    stream = converse(lambda _c, _p: runner, _events_from(_turn(_blob()), _turn()))
    events = [event async for event in stream]
    assert [event.WhichOneof("event") for event in events] == ["turn_complete"] * 2
    assert runner.images == [
        (ImagePart(data=_PNG, mime_type="image/png", width=640, height=480),),
        (),
    ]


async def test_a_full_size_attachment_fits_through_the_brain_server() -> None:
    engine = TurnEngine(InMemorySessionStore(), EchoInferenceBackend(), SystemClock())
    server, port = create_server(
        RpcServerConfig(host="127.0.0.1", port=0), lambda _c, _p: engine, InMemorySessionStore()
    )
    await server.start()
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            opened = BrainServiceStub(channel).Converse  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            call = cast("aio.StreamStreamCall[ClientEvent, ServerEvent]", opened())
            await call.write(_turn(_blob(_PNG + b"\x00" * (MAX_IMAGE_BYTES - len(_PNG)))))
            await call.done_writing()
            kinds = [event.WhichOneof("event") async for event in call]
    finally:
        await server.stop(None)
    assert kinds[-1] == "turn_complete"
