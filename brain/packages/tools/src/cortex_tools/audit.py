"""LoggingAuditSink: the ToolAuditSink that writes the tool audit trail to structured logs.

One `logging` line per dispatched call (ADR-0009 / AGENTS.md audit gate). To keep secrets and
bulk data out of the logs, a successful call logs only its result *size*, not its content
(a file read can be large or sensitive); a failed call logs its short error detail, which is
what an operator actually needs. The arguments (paths, queries) are logged as the audit's
subject. The read-only v1 tools carry no payloads there. Every line carries the result's
``trust`` provenance so "did this turn read untrusted content?" is answerable from the durable
trail alone (ADR-0013 decision 2).
"""

import json
import logging

from cortex_core import ToolInvocation

_logger = logging.getLogger("cortex.tools.audit")


class LoggingAuditSink:
    """ToolAuditSink writing one structured `logging` record per invocation.

    The fields ride the record twice: as `extra` attributes (for structured log collectors)
    and JSON-serialized into the message itself. A plain stdlib formatter shows only the
    message, so without the embedded payload the trail would print bare `tool.invocation`
    lines and the forensic fields would never reach the container logs.
    """

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
