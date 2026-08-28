"""LoggingRecallSink: the RecallAuditSink writing the recall trail to structured logs (ADR-0038).

One `logging` line per recall, answering "why did recall return these?" from the durable trail
rather than from a throwaway script against the store, which is what the question used to need.
Each line carries the pool the store offered, the basis the policy ranked on, whether keys on that
basis may be compared with each other, and one entry per kept hit: its memory id, the store's raw
cosine, the policy's own rank key, and the untrusted-provenance bit.

It also names the candidates the rank did **not** keep, by id and by the store's cosine, bounded
and with a count of whatever the bound left out (ADR-0038 dropped-candidate addendum). A count
alone could not tell "that memory was never a candidate" from "it was a candidate and the rank
dropped it", which is the question an investigation actually arrives with, and the ranks that ship
drop most of the pool. There is no rank key beside a dropped candidate's score because none
exists: a rank records an opinion about what it kept, so the line says what was available rather
than why the rank declined it.

Beside `pool`, which is how many candidates came back, the line carries `available`, which is how
many there were (ADR-0038 candidate-count addendum). Equal, the pool was the whole readable store
and an id on neither list was never written or was written outside the read scopes. Unequal, the
pool was cut at its requested width and an absent memory may only have ranked below the cut. That
reading needs no knowledge of the deployment's pool factor, which is why the requested width is
not logged beside it: where it would matter it equals `pool`, and where it would not it explains
nothing.

A line with no hits is read through its basis, which is why no separate flag is logged for one.
`"basis": "demur"` is the model having read a pool and answered that none of it helps (ADR-0038
abstention addendum); any other basis with an empty `hits` is a pool that held nothing to rank; and
a fallback after an unreachable or unbelievable model shows the fallback's own basis with the hits
it chose. Those are three different events and the trail was collapsing the first onto the last.

What it deliberately does not carry is text. The query and the recalled memories are conversation
content, and container logs are the wrong home for them; the port hands the whole audit over so a
different sink may decide otherwise, and this one logs the query's *length* exactly as the tool
audit logs a result's size rather than its bytes. A dropped candidate is the one place that choice
is not the sink's: the value it is handed carries an id and a score and has no field for text, so
there was nothing here to withhold.
"""

import logging

from cortex_core import RecallAudit

# The name this trail is selected by, on a stream carrying every other line the brain writes. It
# is written here rather than inside the call because three documents restate it and none of them
# can import it, so it is a declaration the constant registry ties them to (ADR-0038 named-logger
# addendum). Naming it also puts it where the rest of this brain's log vocabulary already lives,
# `cortex_core.log_fields` declaring the field names for the same reason.
_LOGGER_NAME = "cortex.memory.recall"

_logger = logging.getLogger(_LOGGER_NAME)


class LoggingRecallSink:
    """RecallAuditSink writing one structured `logging` record per recall.

    The fields ride the record once, as `extra` attributes, and the process entry's formatter
    (`cortex_core.log_format`) is what renders them. They used to ride it twice, JSON-serialized
    into the message as well, because the shipped handler was the stdlib's own and printed the
    message alone; with a formatter that renders fields, a second copy is the same line printed
    twice.

    The conversation rides under `session_id`, which is the brain's one name for it and not this
    trail's own (ADR-0009 one-vocabulary addendum). This sink spelled it `session` for as long as
    it existed, and the rank's fallbacks copied that spelling to sit beside it, while every other
    line in the brain spelled the same fact `session_id`; a grep for either therefore returned
    half the evidence about one conversation. The trail moved because the other name is the one
    the seam, the stores and the dispatch stamp all carry.
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
