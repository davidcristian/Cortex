"""LoggingRecallSink: the RecallAuditSink writing the recall trail to structured logs (ADR-0038).

One `logging` line per recall, answering "why did recall return these?" from the durable trail
rather than from a throwaway script against the store, which is what the question used to need.
Each line carries the pool the store offered, the basis the policy ranked on, whether keys on that
basis may be compared with each other, and one entry per kept hit: its memory id, the store's raw
cosine, the policy's own rank key, and the untrusted-provenance bit.

What it deliberately does not carry is text. The query and the recalled memories are conversation
content, and container logs are the wrong home for them; the port hands the whole audit over so a
different sink may decide otherwise, and this one logs the query's *length* exactly as the tool
audit logs a result's size rather than its bytes.
"""

import json
import logging

from cortex_core import RecallAudit

_logger = logging.getLogger("cortex.memory.recall")


class LoggingRecallSink:
    """RecallAuditSink writing one structured `logging` record per recall.

    The fields ride the record twice, as `extra` attributes for a structured collector and
    JSON-serialized into the message, because a plain stdlib formatter shows only the message and
    the trail would otherwise print bare `memory.recall` lines (the tool audit's adapter learned
    the same thing).
    """

    async def record(self, audit: RecallAudit) -> None:
        """Log one recall: the pool, the basis, and each kept hit's id, score and rank key."""
        fields: dict[str, object] = {
            "session": audit.session_id,
            "query_chars": len(audit.query),
            "pool": audit.pool_size,
            "k": audit.k,
            "basis": audit.ranking.basis.value,
            "keys_comparable": audit.ranking.basis.comparable,
            "hits": [
                {
                    "id": ranked.hit.record.id,
                    "score": ranked.hit.score,
                    "key": ranked.key,
                    "tainted": ranked.hit.record.tainted,
                }
                for ranked in audit.ranking.hits
            ],
            "at": audit.at.isoformat(),
        }
        payload = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
        _logger.info("memory.recall %s", payload, extra=fields)
