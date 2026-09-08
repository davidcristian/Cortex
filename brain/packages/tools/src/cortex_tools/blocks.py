"""Reading an MCP result's image blocks into the core's `ImagePart` values."""

import base64
import binascii

from mcp.types import CallToolResult, ImageContent

from cortex_core.images import ImageError, ImagePart
from cortex_tools.headers import image_size


def _image_part(block: ImageContent) -> ImagePart:
    """One `ImageContent` block as an `ImagePart`, sized from its bytes and typed from its field."""
    try:
        data = base64.b64decode(block.data, validate=True)
    except binascii.Error as err:
        msg = "an MCP image block is not valid base64"
        raise ImageError(msg) from err
    width, height = image_size(data)
    return ImagePart(data=data, mime_type=block.mimeType, width=width, height=height)


def result_images(result: CallToolResult) -> tuple[ImagePart, ...]:
    """Every image block of ``result``, in wire order, as `ImagePart`s."""
    return tuple(_image_part(block) for block in result.content if isinstance(block, ImageContent))
