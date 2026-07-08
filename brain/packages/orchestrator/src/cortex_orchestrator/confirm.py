"""SeamConfirmer: the real ``Confirmer`` adapter over the Converse stream (ADR-0022).

One instance per ``_ConverseStream``, bound to that stream's output queue. That way a pending
confirmation is turn-local by construction: it lives only in the awaiting coroutine, is
denied on timeout, and dies (as a denial) with the stream. Nothing is persisted and nothing
survives the turn; re-asking is the recovery from any interruption (the one hard rule).

The request rides the stream's **control path** (the emit callback is the queue's
``put_nowait``, bypassing the data-credit semaphore exactly like the terminal ``SeamError``):
the turn task is suspended *inside* the dispatcher awaiting the answer, so a credit-acquired
put could deadlock against a stalled consumer. At most one confirmation is outstanding per
stream (turns are sequential, the tool loop is sequential, subagents cannot confirm per
ADR-0013), so the unbounded queue grows by at most one control event.
"""

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
    """Emit a ``ConfirmRequest`` to the overlay and await the user's answer (fail-closed).

    ``confirm`` resolves ``False`` on timeout, after ``close`` (client input ended, so no
    answer can ever arrive), and for any answer that does not match a pending request; a
    cancellation (the turn or stream dying) propagates, denying by never running the tool.
    The human authorizes out of band; the model never does (ADR-0013).
    """

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
        """Deny everything pending and every future ask. Client input has ended.

        Idempotent; called when the request stream half-closes or the pump dies, because
        no answer can ever arrive after that. A turn still draining afterwards sees its
        gated calls declined instead of hanging out the timeout.
        """
        self._closed = True
        for future in self._pending.values():
            if not future.done():
                future.set_result(False)
