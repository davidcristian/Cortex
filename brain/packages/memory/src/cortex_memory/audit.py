"""LoggingRecallSink: the RecallAuditSink writing the recall trail to structured logs (ADR-0038).

One `logging` line per recall, so "why did recall return these?" is answerable from the durable
trail rather than from a throwaway script against the store. Each line carries the pool the store
offered, how many candidates were available to it, the basis the policy ranked on, one entry per
kept hit, and the candidates the rank dropped.

The line carries no text at all, neither the query nor a recalled memory: conversation content
does not belong in container logs, so the query is logged by length, as the tool audit logs a
result's size rather than its bytes. The port hands the whole audit over, so a different sink may
choose otherwise. docs/modules/brain-memory.md states the full field contract, and ADR-0038
argues each field, including why a dropped candidate carries no rank key and why an empty `hits`
is read through the basis beside it.
"""

import logging

from cortex_core import RecallAudit

# The name an operator selects this trail by, on a stream carrying every other line the brain
# writes. Bound here rather than passed inline to `getLogger` because three documents restate it
# and none of them can import it, so `crosscheck.py` ties them to this declaration (ADR-0038
# named-logger addendum).
_LOGGER_NAME = "cortex.memory.recall"

_logger = logging.getLogger(_LOGGER_NAME)


class LoggingRecallSink:
    """RecallAuditSink writing one structured `logging` record per recall.

    The fields ride the record once, as `extra` attributes, and the process entry's formatter
    (`cortex_core.log_format`) renders them. They used to ride it twice, JSON-serialized into the
    message as well, because the shipped handler was the stdlib's own and printed the message
    alone; once the formatter rendered fields, the second copy printed the same line twice.

    The conversation rides under `session_id`, the name the seam, the stores and the dispatch
    stamp all use (ADR-0009 one-vocabulary addendum). This sink called it `session` until then,
    and the rank's fallbacks copied that name, so a grep for either returned half the evidence
    about one conversation.
    """

    async def record(self, audit: RecallAudit) -> None:
        """Log one recall: the pool, what it was drawn from, the basis, the hits, and the drops."""
        fields: dict[str, object] = {
            "session_id": audit.session_id,
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
                {"id": candidate.id, "score": candidate.score}
                for candidate in audit.dropped.carried
            ],
            "dropped_omitted": audit.dropped.omitted,
            "at": audit.at.isoformat(),
        }
        _logger.info("memory.recall", extra=fields)
