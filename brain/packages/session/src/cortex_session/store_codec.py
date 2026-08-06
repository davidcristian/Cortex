"""Keys and record codecs for ``RedisSessionStore``: what a session looks like on the wire.

Split out of ``store.py`` for the line cap when the summarizing window's recap became a second
kind of record (the ``handoff_codec``/``schedule_codec`` precedent), and it is a real seam
rather than a file-size trick: everything here is the STORAGE FORMAT, so a change to how a
session is laid out in Redis is a change to this module, while ``store.py`` stays the round
trips and the error wrapping.

Both record kinds carry ``"v"``/``"kind"`` as the schema escape hatch, and both readers follow
one policy: unknown EXTRA keys are ignored (forward-compatible additions), while an unknown kind
or unsupported version fails LOUDLY naming the record and is never a silent skip, which would
invisibly corrupt a future handoff's context. Failures leave here as ``SessionStoreError``.
"""

import json
from datetime import datetime
from typing import cast

from cortex_core import Message, Role, SessionStoreError
from cortex_core.sessions import HistoryRecap

# The record schema this writer emits and the ONLY combination this reader accepts.
# Records missing the markers decode as this combination (pre-versioning writers).
RECORD_KIND = "message"
RECORD_VERSION = 1

# The recap record's own kind, under the same versioning escape hatch as a message record
# (ADR-0038 decision 9). It is a JSON document rather than a plain string because a recap is
# a pair (the text and the boundary it covers) and half of it would be worse than none.
RECAP_KIND = "recap"


def messages_key(session_id: str) -> str:
    return f"cortex:session:{session_id}:messages"


def title_key(session_id: str) -> str:
    return f"cortex:session:{session_id}:title"


def recap_key(session_id: str) -> str:
    return f"cortex:session:{session_id}:recap"


def encode_message(message: Message) -> str:
    return json.dumps(
        {
            "v": RECORD_VERSION,
            "kind": RECORD_KIND,
            "role": message.role.value,
            "text": message.text,
            "at": message.at.isoformat(),
            "turn_id": message.turn_id,
        }
    )


def refuse_images(message: Message) -> None:
    """Raise if ``message`` carries pixels. See ``RedisSessionStore.append``."""
    if message.images:
        msg = "a session store never persists images: pixels are turn-local"
        raise SessionStoreError(msg)


def decode_message(raw: bytes | str, index: int) -> Message:
    """Decode the record at ``index``; every failure names that record precisely.

    Only the known keys are read, so unknown extra keys pass through untouched; an
    unknown kind/version raises BEFORE field decoding so future record shapes fail
    with the precise message, not as an arbitrary missing-field error.
    """
    try:
        fields = cast("dict[str, str]", json.loads(raw))
        kind = fields.get("kind", RECORD_KIND)
        version = fields.get("v", RECORD_VERSION)
        if kind != RECORD_KIND or version != RECORD_VERSION:
            msg = (
                f"unreadable session record at index {index}: kind {kind!r} v {version!r}"
                f" (this reader supports kind {RECORD_KIND!r} v {RECORD_VERSION})"
            )
            raise SessionStoreError(msg)
        return Message(
            role=Role(fields["role"]),
            text=fields["text"],
            at=datetime.fromisoformat(fields["at"]),
            turn_id=fields["turn_id"],
        )
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        # AttributeError: a JSON document that is not an object has no .get.
        msg = f"corrupt session record at index {index}"
        raise SessionStoreError(msg) from err


def encode_recap(recap: HistoryRecap) -> str:
    """The recap document: the text the model wrote and the boundary it accounts for.

    Both halves go on the wire because a reader with the text alone could not tell a current
    recap from a stale one, and would prepend the wrong paragraph for the rest of the session.
    """
    return json.dumps(
        {"v": RECORD_VERSION, "kind": RECAP_KIND, "text": recap.text, "covers": recap.covers}
    )


def decode_recap(raw: bytes | str, session_id: str) -> HistoryRecap:
    """Decode the stored recap document, failing loudly on anything this reader cannot read.

    A recap is derived and disposable, so a corrupt one could in principle be discarded
    silently; it is not, because a reader that quietly answered "no recap" would look exactly
    like a session that has never been summarized, and would hide a schema mistake behind a
    summarizer that merely seems expensive.
    """
    try:
        fields = cast("dict[str, object]", json.loads(raw))
        kind = fields.get("kind", RECAP_KIND)
        version = fields.get("v", RECORD_VERSION)
        if kind != RECAP_KIND or version != RECORD_VERSION:
            msg = (
                f"unreadable recap for session {session_id!r}: kind {kind!r} v {version!r}"
                f" (this reader supports kind {RECAP_KIND!r} v {RECORD_VERSION})"
            )
            raise SessionStoreError(msg)
        return HistoryRecap(text=cast("str", fields["text"]), covers=cast("int", fields["covers"]))
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        # ValueError also covers HistoryRecap's own rejection of a blank text / zero boundary.
        msg = f"corrupt recap for session {session_id!r}"
        raise SessionStoreError(msg) from err
