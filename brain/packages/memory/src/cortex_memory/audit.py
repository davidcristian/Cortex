"""LoggingRecallSink: the RecallAuditSink writing the recall trail to structured logs (ADR-0038)."""

import json
import logging

from cortex_core import RecallAudit

_logger = logging.getLogger("cortex.memory.recall")


class LoggingRecallSink:
    """RecallAuditSink writing one structured `logging` record per recall."""

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
