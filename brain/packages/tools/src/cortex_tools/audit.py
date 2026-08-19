"""LoggingAuditSink: the ToolAuditSink that writes the tool audit trail to structured logs.

One `logging` line per dispatched call (ADR-0009 / AGENTS.md audit gate). To keep secrets and
bulk data out of the logs, a successful call logs only its result *size*, not its content
(a file read can be large or sensitive); a failed call logs its short error detail, which is
what an operator actually needs. The arguments (paths, queries) are logged as the audit's
subject. The read-only v1 tools carry no payloads there. Every line carries the result's
``trust`` provenance so "did this turn read untrusted content?" is answerable from the durable
trail alone (ADR-0013 decision 2).
"""

import logging

from cortex_core import ToolInvocation

_logger = logging.getLogger("cortex.tools.audit")


class LoggingAuditSink:
    """ToolAuditSink writing one structured `logging` record per invocation.

    The fields ride the record once, as `extra` attributes, and the process entry's formatter
    (`cortex_core.log_format`) renders them into the line. They used to be JSON-serialized into
    the message as well, because the shipped handler printed the message alone and the forensic
    fields would otherwise never have reached the container logs; a formatter that renders fields
    makes that copy a duplicate of the same trail.
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
        _logger.info("tool.invocation", extra=fields)
