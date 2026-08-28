"""LoggingAuditSink: the ToolAuditSink that writes the tool audit trail to structured logs.

One `logging` line per dispatched call (ADR-0009 / AGENTS.md audit gate). To keep secrets and
bulk data out of the logs, a successful call logs only its result *size*, not its content
(a file read can be large or sensitive); a failed call logs its short error detail, which is
what an operator actually needs. The arguments (paths, queries) are logged as the audit's
subject. The read-only v1 tools carry no payloads there. Every line carries the result's
``trust`` provenance so "did this turn read untrusted content?" is answerable from the durable
trail alone (ADR-0013 decision 2), and the identities of the work it was for so the same trail
answers "what did this turn do?" and "what did its subagents do?" (ADR-0009 named-work addendum).
"""

import logging

from cortex_core import ToolInvocation
from cortex_core.log_fields import (
    CALL_FIELD,
    ITEM_FIELD,
    SESSION_FIELD,
    TASK_FIELD,
    TURN_FIELD,
)

# The name this trail is selected by, on a stream carrying every other line the brain writes. It
# is written here rather than inside the call because four places restate it and none of them can
# import it, two runbooks telling an operator what to select, a sibling module's docstring arguing
# from it that the shipped level is not a knob, and that module's suite proving the argument, so it
# is a declaration the constant registry ties them to (ADR-0009 audit-logger addendum). The recall
# trail's sink names its own logger the same way, and for the same reason.
_LOGGER_NAME = "cortex.tools.audit"

_logger = logging.getLogger(_LOGGER_NAME)


class LoggingAuditSink:
    """ToolAuditSink writing one structured `logging` record per invocation.

    The fields ride the record once, as `extra` attributes, and the process entry's formatter
    (`cortex_core.log_format`) renders them into the line. They used to be JSON-serialized into
    the message as well, because the shipped handler printed the message alone and the forensic
    fields would otherwise never have reached the container logs; a formatter that renders fields
    makes that copy a duplicate of the same trail.
    """

    async def record(self, invocation: ToolInvocation) -> None:
        """Log the invocation: name, ok, arguments, trust, timestamp; detail only on failure.

        Then which call it was and what it was made for (ADR-0009 named-work and named-call
        addenda), under the same field names the rest of this repo's log lines spell those ids
        with, so an operator reading a failed turn's line can grep its `turn_id` and get the tool
        calls that preceded it. An id the dispatch did not have is left off the line rather than
        printed empty: absence is the honest rendering of an unattributed caller, and an empty
        field would read as a missing value rather than as no such thing.

        The five ids print alike and are read differently, which is the field name's job.
        `session_id`, `turn_id`, `task_id` and `item_id` are off the dispatch stamp, which the
        dispatcher overwrites, so they are what the brain knows about the work; `call_id` is the
        call's own, which on a cortex dispatch is whatever the model emitted, so it is read the
        way `tool` and `arguments` are read. The formatter is what makes printing that safe: a
        rendered value carrying whitespace or a quote is quoted and escaped, so no id can forge
        a field boundary, and an over-long one is cut with a marker.

        The five names come from `cortex_core.log_fields` rather than being written here, this
        being the one sink that writes the whole vocabulary out as a list and so the one place
        where naming each element costs nothing a reader wanted (ADR-0009 one-vocabulary
        addendum). Every other line in the brain names one identity inside its own `extra=` and
        keeps the literal there, where the string an operator greps is what a reader came for.
        """
        fields: dict[str, object] = {
            "tool": invocation.name,
            "ok": invocation.ok,
            "arguments": dict(invocation.arguments),
            "trust": invocation.trust.value,
            "at": invocation.at.isoformat(),
        }
        fields.update(
            {
                name: identity
                for name, identity in (
                    (CALL_FIELD, invocation.call_id),
                    (SESSION_FIELD, invocation.session_id),
                    (TURN_FIELD, invocation.turn_id),
                    (TASK_FIELD, invocation.task_id),
                    (ITEM_FIELD, invocation.item_id),
                )
                if identity
            }
        )
        if invocation.ok:
            fields["result_chars"] = len(invocation.detail)
        else:
            fields["error"] = invocation.detail
        _logger.info("tool.invocation", extra=fields)
