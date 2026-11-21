"""A loopback HTTP server that sends one path's answer a byte at a time."""

import asyncio
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

_HEAD_END = b"\r\n\r\n"
_LENGTH = re.compile(rb"content-length: (\d+)")
_HEAD = b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"


@dataclass
class DripServer:
    """Drips ``slow_body`` on ``slow_path`` and answers every other path with ``reply`` at once."""

    slow_path: str
    slow_body: bytes
    reply: bytes = b""
    pause_s: float = 0.01
    dripped: int = 0
    bodies: list[bytes] = field(default_factory=list[bytes])
    endpoint: str = ""

    async def _answer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await reader.readuntil(_HEAD_END)
        length = _LENGTH.search(head.lower())
        body = await reader.readexactly(int(length[1])) if length else b""
        slow = head.split(b" ")[1].decode() == self.slow_path
        answer = self.slow_body if slow else self.reply
        writer.write(_HEAD % len(answer))
        try:
            if slow:
                for at in range(len(answer)):
                    await asyncio.sleep(self.pause_s)
                    writer.write(answer[at : at + 1])
                    await writer.drain()
                    self.dripped += 1
            else:
                self.bodies.append(body)
                writer.write(answer)
                await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    @asynccontextmanager
    async def serving(self) -> AsyncGenerator["DripServer", None]:
        """Listen on a free loopback port for as long as the block runs."""
        server = await asyncio.start_server(self._answer, "127.0.0.1", 0)
        self.endpoint = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
        try:
            yield self
        finally:
            server.close()
            await server.wait_closed()
