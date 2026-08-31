"""Keys and record codecs for ``RedisSessionStore``: what a session looks like on the wire."""

import json
from datetime import datetime
from typing import cast

from cortex_core import Message, Role, SessionStoreError
from cortex_core.sessions import HistoryRecap

# A record written before these markers existed has neither key, and decodes as this pair.
RECORD_KIND = "message"
RECORD_VERSION = 1

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
    """Raise when ``message`` contains images."""
    if message.images:
        msg = "a session store never persists images: pixels are turn-local"
        raise SessionStoreError(msg)


def decode_message(raw: bytes | str, index: int) -> Message:
    """Decode the record at ``index``; every failure names that record precisely."""
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
    # AttributeError: a JSON document that is not an object has no .get.
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        msg = f"corrupt session record at index {index}"
        raise SessionStoreError(msg) from err


def encode_recap(recap: HistoryRecap) -> str:
    """The recap document: the text the model wrote and the boundary it accounts for."""
    return json.dumps(
        {"v": RECORD_VERSION, "kind": RECAP_KIND, "text": recap.text, "covers": recap.covers}
    )


def decode_recap(raw: bytes | str, session_id: str) -> HistoryRecap:
    """Decode the stored recap document, raising on anything this reader cannot read."""
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
        msg = f"corrupt recap for session {session_id!r}"
        raise SessionStoreError(msg) from err
