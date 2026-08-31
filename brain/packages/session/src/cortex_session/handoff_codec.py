"""Codec for the Redis ``HandoffStore``: one ``HandoffRecord`` as one JSON document (ADR-0030).

Hot, short-lived state on the ``TaskStore`` precedent: a handoff record is written and read
back within one handoff (minutes) by one deployment, so it carries no ``v``/``kind`` markers,
and a missing key is a corrupt record that raises ``HandoffStoreError`` naming its key rather
than being skipped (dropping the taint fields with nothing reporting it would fail open after the
swap). The whole record round-trips: the taint ledger's two bits (``tainted``, and the ``opaque``
bit that says the untrusted content was unfenceable, ADR-0029), its sources in read order (each
kind's string plus its already-sanitized value), the laundering-evidence URL set (stored sorted
for a deterministic document, read back as a set), the budget position, and the tool-loop tail
with each message's tool calls. A tool call's ``stamp`` is a transient live handle and is never
persisted (``tools.py``: the loop persists the unstamped calls), so a decoded call carries the
default ``UNSTAMPED``, exactly as the loop appended it.

``failure`` travels in the same document under the same rule, ``null`` on every record that has
not been settled failed. It is written last because it is the only field written after the
snapshot, and it is a required key like the rest: a document without it is a record from something
that is not this codec, and reading one as "no reason given" would be indistinguishable from a
handoff that really was settled without one, which is the state this field exists to end.
"""

import json
from datetime import datetime
from typing import Any, cast

from cortex_core import (
    HandoffRecord,
    HandoffState,
    HandoffStoreError,
    Message,
    Provenance,
    Role,
    SourceKind,
    ToolCall,
)


def record_key(handoff_id: str) -> str:
    """The Redis key holding one handoff record."""
    return f"cortex:handoff:{handoff_id}"


# The single-active-handoff pointer (one GPU, at most one swap in flight): holds the id of the
# non-terminal record, maintained by every write, read by `active()`.
ACTIVE_KEY = "cortex:handoff:active"


def _encode_message(message: Message) -> dict[str, Any]:
    return {
        "role": message.role.value,
        "text": message.text,
        "at": message.at.isoformat(),
        "turn_id": message.turn_id,
        "tool_calls": [
            {"id": call.id, "name": call.name, "arguments": dict(call.arguments)}
            for call in message.tool_calls
        ],
        "tool_call_id": message.tool_call_id,
    }


def _decode_message(fields: dict[str, Any]) -> Message:
    return Message(
        role=Role(fields["role"]),
        text=fields["text"],
        at=datetime.fromisoformat(fields["at"]),
        turn_id=fields["turn_id"],
        tool_calls=tuple(
            ToolCall(id=call["id"], name=call["name"], arguments=call["arguments"])
            for call in fields["tool_calls"]
        ),
        tool_call_id=fields["tool_call_id"],
    )


def encode_record(record: HandoffRecord) -> str:
    """Serialize one record; the reader below accepts exactly this shape."""
    return json.dumps(
        {
            "handoff_id": record.handoff_id,
            "session_id": record.session_id,
            "requested_at": record.requested_at.isoformat(),
            "state": record.state.value,
            "brief": record.brief,
            "nonce": record.nonce,
            "tainted": record.tainted,
            "opaque": record.opaque,
            "sources": [
                {"kind": source.kind.value, "value": source.value} for source in record.sources
            ],
            "untrusted_urls": sorted(record.untrusted_urls),
            "budget_remaining": record.budget_remaining,
            "budget_closed": record.budget_closed,
            "rounds_used": record.rounds_used,
            "loop_tail": [_encode_message(message) for message in record.loop_tail],
            "failure": record.failure,
        }
    )


def decode_record(raw: bytes | str, handoff_id: str) -> HandoffRecord:
    """Decode one record; every failure names the record's key precisely."""
    try:
        fields = cast("dict[str, Any]", json.loads(raw))
        return HandoffRecord(
            handoff_id=fields["handoff_id"],
            session_id=fields["session_id"],
            requested_at=datetime.fromisoformat(fields["requested_at"]),
            state=HandoffState(fields["state"]),
            brief=fields["brief"],
            nonce=fields["nonce"],
            tainted=fields["tainted"],
            opaque=fields["opaque"],
            sources=tuple(
                Provenance(kind=SourceKind(source["kind"]), value=source["value"])
                for source in fields["sources"]
            ),
            untrusted_urls=frozenset(fields["untrusted_urls"]),
            budget_remaining=fields["budget_remaining"],
            budget_closed=fields["budget_closed"],
            rounds_used=fields["rounds_used"],
            loop_tail=tuple(_decode_message(message) for message in fields["loop_tail"]),
            failure=fields["failure"],
        )
    except (KeyError, TypeError, ValueError) as err:
        msg = f"corrupt handoff record at {record_key(handoff_id)!r}"
        raise HandoffStoreError(msg) from err
