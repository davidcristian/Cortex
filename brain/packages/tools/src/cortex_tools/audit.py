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

# The name an operator selects this trail by, and the word every audited line opens with. Bound
# here because four places restate them and none can import them: two runbooks, a sibling
# module's docstring and that module's suite. `crosscheck.py` ties all four to these.
_LOGGER_NAME = "cortex.tools.audit"

_MESSAGE = "tool.invocation"

_logger = logging.getLogger(_LOGGER_NAME)


def invocation_fields(invocation: ToolInvocation) -> dict[str, object]:
    """The fields one audit record has: name, ok, arguments, trust, time, detail on failure."""
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
    return fields


class LoggingAuditSink:
    """ToolAuditSink writing one structured `logging` record per invocation."""

    async def record(self, invocation: ToolInvocation) -> None:
        """Log the invocation's fields, as `invocation_fields` builds them."""
        fields = invocation_fields(invocation)
        _logger.info(_MESSAGE, extra=fields)
