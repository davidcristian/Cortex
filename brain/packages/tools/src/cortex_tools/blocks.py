"""Reading an MCP result's image blocks into the core's `ImagePart` values (ADR-0009).

An MCP `ImageContent` block carries base64 bytes and a declared mime type and states no
dimensions, while `ImagePart` requires a width and a height. This module decodes the base64 and
hands the bytes to `cortex_tools.headers`, which states the size for a PNG, a JPEG, or a WebP. A
block in any other format, or whose base64 does not decode, raises `ImageError` for the adapter to
cross the port as `ToolError`.
"""

import base64
import binascii

from mcp.types import CallToolResult, ImageContent

from cortex_core.images import ImageError, ImagePart
from cortex_tools.headers import image_size


def _image_part(block: ImageContent) -> ImagePart:
    """One `ImageContent` block as an `ImagePart`, sized from its bytes and typed from its field.

    The mime type is the sidecar's declaration and is checked against the core's allow-list rather
    than against the bytes, which is the same standing the body's declared type has. The reader is
    chosen by the signature the bytes carry, not by that declaration.
    """
    try:
        data = base64.b64decode(block.data, validate=True)
    except binascii.Error as err:
        msg = "an MCP image block is not valid base64"
        raise ImageError(msg) from err
    width, height = image_size(data)
    return ImagePart(data=data, mime_type=block.mimeType, width=width, height=height)


def result_images(result: CallToolResult) -> tuple[ImagePart, ...]:
    """Every image block of ``result``, in wire order, as `ImagePart`s.

    Raises ``ImageError`` when any one of them cannot be read, so a result carrying an unreadable
    image fails the call rather than delivering some of its pictures.
    """
    return tuple(_image_part(block) for block in result.content if isinstance(block, ImageContent))
