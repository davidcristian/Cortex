"""LoggingAuditSink: the ToolAuditSink that writes the tool audit trail to structured logs."""

import logging

from cortex_core import ToolInvocation
from cortex_core.log_fields import (
    CALL_FIELD,
    ITEM_FIELD,
    SESSION_FIELD,
    TASK_FIELD,
    TURN_FIELD,
)

_LOGGER_NAME = "cortex.tools.audit"

# The word every audited line opens with, bound here for the same reason as the logger name above
# and against the same restatements in the tools runbook and the process entry's suite (ADR-0009
# audit-message addendum). It is handed to the call below so this module writes the word once.
_MESSAGE = "tool.invocation"

_logger = logging.getLogger(_LOGGER_NAME)


class LoggingAuditSink:
    """ToolAuditSink writing one structured `logging` record per invocation."""

    async def record(self, invocation: ToolInvocation) -> None:
        """Log the invocation: name, ok, arguments, trust, timestamp; detail only on failure."""
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
