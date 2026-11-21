"""One bound over a whole probe exchange: the connection, the headers and the body together."""

import asyncio
from collections.abc import Awaitable

import httpx

__all__ = ["ProbeTimeoutError", "answered_within"]


class ProbeTimeoutError(Exception):
    """The whole answer did not arrive inside the probe's bound."""


async def answered_within(seconds: float, exchange: Awaitable[httpx.Response]) -> httpx.Response:
    """The response of ``exchange``, or ``ProbeTimeoutError`` once ``seconds`` have passed."""
    # A number given to httpx bounds each read, so an answer sent a few bytes at a time outlasts it.
    try:
        async with asyncio.timeout(seconds):
            return await exchange
    except TimeoutError as err:
        msg = f"no whole answer within {seconds:g} s"
        raise ProbeTimeoutError(msg) from err
