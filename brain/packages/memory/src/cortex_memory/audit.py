"""LoggingRecallSink: the RecallAuditSink that writes each recall to the structured logs."""

import logging

from cortex_core import RecallAudit

_LOGGER_NAME = "cortex.memory.recall"

_logger = logging.getLogger(_LOGGER_NAME)


class LoggingRecallSink:
    """RecallAuditSink writing one structured `logging` record per recall."""

    async def record(self, audit: RecallAudit) -> None:
        """Log one recall: the pool, what it was drawn from, the basis, the hits, and the drops."""
        fields: dict[str, object] = {
            "session_id": audit.session_id,
            "turn_id": audit.turn_id,
            "query_chars": len(audit.query),
            "pool": audit.pool_size,
            "available": audit.available,
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
            "dropped": [
                {"id": candidate.id, "score": candidate.score} for candidate in audit.dropped.listed
            ],
            "dropped_omitted": audit.dropped.omitted,
            "at": audit.at.isoformat(),
        }
        _logger.info("memory.recall", extra=fields)
