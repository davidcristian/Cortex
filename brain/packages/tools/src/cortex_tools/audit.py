"""LoggingAuditSink: the ToolAuditSink that writes the tool audit trail to structured logs.

One `logging` line per dispatched call (ADR-0009, and the audit gate in AGENTS.md). To keep
secrets and bulk data out of the logs, a successful call logs only its result size, not its
content, since a file read can be large or sensitive; a failed call logs its short error
detail. Every line also carries the result's ``trust`` provenance and the ids of the work the
call was made for. docs/modules/brain-tools.md states the full field contract.
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

# The name an operator selects this trail by, on a stream carrying every other line the brain
# writes. Bound here rather than passed inline to `getLogger` because four places restate it and
# none of them can import it: two runbooks, a sibling module's docstring, and that module's suite.
# `crosscheck.py` ties all four to this declaration (ADR-0009 audit-logger addendum).
_LOGGER_NAME = "cortex.tools.audit"

# The word every audited line opens with, bound here for the same reason as the logger name above
# and against the same restatements in the tools runbook and the process entry's suite (ADR-0009
# audit-message addendum). It is handed to the call below so this module writes the word once.
_MESSAGE = "tool.invocation"

_logger = logging.getLogger(_LOGGER_NAME)


class LoggingAuditSink:
    """ToolAuditSink writing one structured `logging` record per invocation.

    The fields ride the record once, as `extra` attributes, and the process entry's formatter
    (`cortex_core.log_format`) renders them into the line. They used to be JSON-serialized into
    the message as well, because the shipped handler printed the message alone and the fields
    would otherwise never have reached the container logs; once the formatter rendered fields,
    that copy was a duplicate.
    """

    async def record(self, invocation: ToolInvocation) -> None:
        """Log the invocation: name, ok, arguments, trust, timestamp; detail only on failure.

        Then which call it was and what it was made for (ADR-0009 named-work and named-call
        addenda), under the same field names the rest of this repo's log lines use for those ids,
        so an operator reading a failed turn's line can grep its `turn_id` and get the tool calls
        that preceded it. An id the dispatch did not carry is left off the line rather than
        printed empty, since an empty field would read as a missing value.

        `session_id`, `turn_id`, `task_id` and `item_id` come off the dispatch stamp, which the
        dispatcher overwrites. `call_id` is the call's own, which on a cortex dispatch is whatever
        the model emitted, so it is as untrusted as `tool` and `arguments`; the formatter quotes
        and escapes a rendered value carrying whitespace or a quote, so no id can forge a field
        boundary, and cuts an over-long one with a marker.

        The five names come from `cortex_core.log_fields` rather than being written here, this
        being the one sink that writes the whole vocabulary out as a list (ADR-0009
        one-vocabulary addendum). Every other line in the brain names one identity inside its own
        `extra=` and keeps the literal there, where an operator greps it.
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
        _logger.info(_MESSAGE, extra=fields)
