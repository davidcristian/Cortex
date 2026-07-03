"""LoggingAuditSink: the ToolAuditSink that writes the tool audit trail to structured logs."""

import json
import logging

from cortex_core import ToolInvocation

_logger = logging.getLogger("cortex.tools.audit")


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
        if invocation.ok:
            fields["result_chars"] = len(invocation.detail)
        else:
            fields["error"] = invocation.detail
        payload = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
        _logger.info("tool.invocation %s", payload, extra=fields)
