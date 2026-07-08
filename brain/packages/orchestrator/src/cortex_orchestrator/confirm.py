"""SeamConfirmer: the real ``Confirmer`` adapter over the Converse stream (ADR-0022)."""

import asyncio
import json
import logging
import uuid
from collections.abc import Callable

from cortex_core import ConfirmationRequest
from cortex_seam import ConfirmRequest as ConfirmRequestPb
from cortex_seam import ServerEvent

_logger = logging.getLogger(__name__)


class SeamConfirmer:
    """Emit a ``ConfirmRequest`` to the overlay and await the user's answer (fail-closed)."""

    def __init__(self, emit: Callable[[ServerEvent], None], *, timeout_s: float) -> None:
        self._emit = emit
        self._timeout_s = timeout_s
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self._closed = False

    async def confirm(self, request: ConfirmationRequest) -> bool:
        """Ask the user to approve ``request``; only an explicit, timely approval is True."""
        if self._closed:
            return False
        confirm_id = uuid.uuid4().hex
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending[confirm_id] = future
        try:
            self._emit(
                ServerEvent(
                    confirm_request=ConfirmRequestPb(
                        confirm_id=confirm_id,
                        tool_name=request.tool_name,
                        # The draft shown is the draft executed (ADR-0022 risk note);
                        # default=str keeps an exotic value displayable, never a crash.
                        arguments_json=json.dumps(
                            dict(request.arguments), ensure_ascii=False, default=str
                        ),
                        reason=request.reason,
                    )
                )
            )
            async with asyncio.timeout(self._timeout_s):
                return await future
        except TimeoutError:
            _logger.info("confirmation timed out; denying", extra={"tool": request.tool_name})
            return False
        finally:
            # Runs on answer, timeout, and cancellation alike: once deregistered, a late
            # answer is a stale id and resolves nothing (the denial already happened).
            self._pending.pop(confirm_id, None)

    def resolve(self, confirm_id: str, *, approved: bool) -> None:
        """Route one ``ConfirmResponse`` to its awaiting request; unknown ids are ignored."""
        future = self._pending.get(confirm_id)
        if future is None or future.done():
            _logger.debug("ignoring stale or unknown confirm id", extra={"id": confirm_id})
            return
        future.set_result(approved)

    def close(self) -> None:
        """Deny everything pending and every future ask. Client input has ended."""
        self._closed = True
        for future in self._pending.values():
            if not future.done():
                future.set_result(False)
