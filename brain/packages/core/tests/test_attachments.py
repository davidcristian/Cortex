from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    MAX_ATTACHED_IMAGES,
    MAX_IMAGE_BYTES,
    MAX_TURN_MESSAGE_BYTES,
    SECURITY_PREAMBLE,
    AttachmentError,
    EscalationSlot,
    GenerationBounds,
    HashEmbedder,
    ImagePart,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    Message,
    Role,
    SystemClock,
    TaintLedger,
    TextChunk,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    check_attachments,
)
from cortex_core.attachments import (
    ATTACHMENT_FRAME,
    attach_images,
    attachment_note,
    signature_matches,
)

_AT = datetime(2026, 9, 25, 3, 0, tzinfo=UTC)
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
_WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


class _FixedClock:
    def now(self) -> datetime:
        return _AT


def _part(data: bytes = _PNG, mime_type: str = "image/png") -> ImagePart:
    return ImagePart(data=data, mime_type=mime_type, width=640, height=480)


@pytest.mark.parametrize(
    ("data", "mime_type"),
    [(_PNG, "image/png"), (_JPEG, "image/jpeg"), (_WEBP, "image/webp")],
)
def test_each_allowed_type_is_recognised_by_its_signature(data: bytes, mime_type: str) -> None:
    assert signature_matches(_part(data, mime_type))


@pytest.mark.parametrize(
    ("data", "mime_type"),
    [
        (_JPEG, "image/png"),
        (_PNG, "image/jpeg"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "image/webp"),
        (b"RIFX\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"\x89PN", "image/png"),
    ],
)
def test_bytes_that_are_not_the_declared_type_are_refused(data: bytes, mime_type: str) -> None:
    with pytest.raises(AttachmentError, match=f"attachment 1 is declared {mime_type}"):
        check_attachments([_part(data, mime_type)])


def test_the_second_bad_attachment_is_named_by_its_position() -> None:
    with pytest.raises(AttachmentError, match="attachment 2 is declared image/png"):
        check_attachments([_part(), _part(_JPEG, "image/png")])


def test_the_most_a_turn_may_attach_is_accepted_and_one_more_is_refused() -> None:
    assert len(check_attachments([_part()] * MAX_ATTACHED_IMAGES)) == MAX_ATTACHED_IMAGES
    with pytest.raises(AttachmentError, match=f"at most {MAX_ATTACHED_IMAGES} images"):
        check_attachments([_part()] * (MAX_ATTACHED_IMAGES + 1))


def test_a_turn_message_fits_every_attachment_at_its_byte_cap() -> None:
    assert MAX_TURN_MESSAGE_BYTES > MAX_ATTACHED_IMAGES * MAX_IMAGE_BYTES


def test_the_note_names_each_attachment_and_is_empty_without_one() -> None:
    assert attachment_note(()) == ""
    assert attachment_note([_part(), _part(_JPEG, "image/jpeg")]) == (
        "\n\n(Attached to this message and not kept: image/png 640x480, image/jpeg 640x480.)"
    )


def test_attach_images_gives_back_only_the_stored_user_message() -> None:
    earlier = Message(role=Role.USER, text="hi", at=_AT, turn_id="t-0")
    stored = Message(
        role=Role.USER, text="what is this" + attachment_note([_part()]), at=_AT, turn_id="t-1"
    )
    working = attach_images([earlier, stored], stored, text="what is this", images=(_part(),))
    assert working[0] is earlier
    assert working[1] == Message(
        role=Role.USER,
        text="what is this" + ATTACHMENT_FRAME,
        at=_AT,
        turn_id="t-1",
        images=(_part(),),
    )


def test_an_attachment_taints_the_ledger_and_makes_it_opaque() -> None:
    ledger = TaintLedger()
    ledger.observe_attachment()
    assert (ledger.tainted, ledger.opaque) == (True, True)


class _Recording:
    def __init__(self) -> None:
        self.seen: list[tuple[Message, ...]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.seen.append(tuple(messages))
        yield TextChunk("a red bicycle")


async def _turn(
    engine: TurnEngine, images: tuple[ImagePart, ...], text: str = "what is this?"
) -> None:
    async for _event in engine.handle_turn("s", text, turn_id="t-1", images=images):
        pass


async def test_the_model_sees_the_pixels_on_the_user_message_with_the_typed_text() -> None:
    backend = _Recording()
    engine = TurnEngine(InMemorySessionStore(), backend, _FixedClock())
    await _turn(engine, (_part(),))
    sent = backend.seen[0]
    assert sent[-1] == Message(
        role=Role.USER,
        text="what is this?" + ATTACHMENT_FRAME,
        at=_AT,
        turn_id="t-1",
        images=(_part(),),
    )
    assert sent[0].text == SECURITY_PREAMBLE


async def test_history_keeps_the_note_and_never_the_pixels() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, _Recording(), _FixedClock())
    await _turn(engine, (_part(),))
    user, reply = await store.history("s")
    assert user.text == "what is this?" + attachment_note([_part()])
    assert user.images == ()
    assert reply.text == "a red bicycle"


async def test_a_turn_with_an_attachment_is_opaque_and_records_no_memory() -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    slot = EscalationSlot()
    engine = TurnEngine(
        InMemorySessionStore(),
        _Recording(),
        _FixedClock(),
        capabilities=TurnCapabilities(memory=recaller, record_tainted_memory=True, escalation=slot),
    )
    await _turn(engine, (_part(),), text="bicycle")
    assert slot.refs is not None
    assert (slot.refs.taint.tainted, slot.refs.taint.opaque) == (True, True)
    assert list(await recaller.recall("bicycle", k=1, session_id="s", turn_id="t")) == []


async def test_a_turn_without_attachments_stores_the_text_as_typed_and_stays_clean() -> None:
    store = InMemorySessionStore()
    slot = EscalationSlot()
    engine = TurnEngine(
        store, _Recording(), _FixedClock(), capabilities=TurnCapabilities(escalation=slot)
    )
    await _turn(engine, ())
    assert (await store.history("s"))[0].text == "what is this?"
    assert slot.refs is not None
    assert (slot.refs.taint.tainted, slot.refs.taint.opaque) == (False, False)
