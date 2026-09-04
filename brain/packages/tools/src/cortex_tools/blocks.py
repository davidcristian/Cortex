"""Reading an MCP result's image blocks into the core's `ImagePart` values (ADR-0009).

An MCP `ImageContent` block carries base64 bytes and a declared mime type and states no
dimensions, while `ImagePart` requires a width and a height. This module supplies them from the
PNG header, which is the only format it reads: a block that is not a PNG, or whose base64 does not
decode, raises `ImageError` for the adapter to cross the port as `ToolError`.

Reading the header is a fixed-offset read of eight bytes after a signature comparison. Nothing
here follows a length the bytes state and nothing reaches a pixel, so the posture
`cortex_core.images` sets out, that no attacker-controlled bytes reach a decoder inside the
process holding the durable memory store, still holds with this module in it.
"""

import base64
import binascii
import struct

from mcp.types import CallToolResult, ImageContent

from cortex_core.images import ImageError, ImagePart

# PNG states its dimensions in the IHDR chunk, which the format requires first: an 8 byte
# signature, the chunk's 4 byte length and 4 byte type, then width and height as big-endian
# unsigned 32 bit integers at bytes 16 to 24.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SIZE_START = 16
_SIZE_END = 24


def _png_size(data: bytes) -> tuple[int, int]:
    """The width and height PNG's IHDR chunk states; ``ImageError`` for anything else."""
    if not data.startswith(_PNG_SIGNATURE):
        msg = "an MCP image block is not a PNG, the one format whose size this reads"
        raise ImageError(msg)
    if len(data) < _SIZE_END:
        msg = f"an MCP image block is {len(data)} bytes, too few to carry a PNG header"
        raise ImageError(msg)
    width, height = struct.unpack(">II", data[_SIZE_START:_SIZE_END])
    return width, height


def _image_part(block: ImageContent) -> ImagePart:
    """One `ImageContent` block as an `ImagePart`, sized from its bytes and typed from its field.

    The mime type is the sidecar's declaration and is checked against the core's allow-list rather
    than against the bytes, which is the same standing the body's declared type has. A declaration
    disagreeing with the bytes fails anyway, since only a PNG has a size to read.
    """
    try:
        data = base64.b64decode(block.data, validate=True)
    except binascii.Error as err:
        msg = "an MCP image block is not valid base64"
        raise ImageError(msg) from err
    width, height = _png_size(data)
    return ImagePart(data=data, mime_type=block.mimeType, width=width, height=height)


def result_images(result: CallToolResult) -> tuple[ImagePart, ...]:
    """Every image block of ``result``, in wire order, as `ImagePart`s.

    Raises ``ImageError`` when any one of them cannot be read, so a result carrying an unreadable
    image fails the call rather than delivering some of its pictures.
    """
    return tuple(_image_part(block) for block in result.content if isinstance(block, ImageContent))
