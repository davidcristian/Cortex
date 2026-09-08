"""Behavior tests for the MCP image-block reader (`cortex_tools.blocks`, ADR-0009).

The reader supplies the width and height `ImagePart` requires out of the bytes, because an MCP
`ImageContent` block states no dimensions. Every way a block can fail to yield one is `ImageError`,
which `McpToolRegistry.invoke` crosses the port as `ToolError`. What each container header states
is `test_headers.py`; what this file holds is the path from a block to an `ImagePart`.
"""

import base64
import struct

import pytest
from mcp.types import CallToolResult, ImageContent, TextContent
from pictures import (
    JPEG_BYTES,
    LOSSY_WEBP_BYTES,
    PNG_BASE64,
    PNG_BYTES,
    PNG_HEIGHT,
    PNG_WIDTH,
    SAMPLE_HEIGHT,
    SAMPLE_WIDTH,
)

from cortex_core.images import MAX_IMAGE_EDGE, ImageError
from cortex_tools.blocks import result_images


def _block(data: bytes, mime: str = "image/png") -> ImageContent:
    return ImageContent(type="image", data=base64.b64encode(data).decode("ascii"), mimeType=mime)


def _resized(width: int, height: int) -> bytes:
    """The shared PNG with its IHDR width and height overwritten, header bytes only."""
    return PNG_BYTES[:16] + struct.pack(">II", width, height) + PNG_BYTES[24:]


def test_an_image_block_is_read_at_the_size_its_header_states() -> None:
    result = CallToolResult(
        content=[
            TextContent(type="text", text="a chart"),
            ImageContent(type="image", data=PNG_BASE64, mimeType="image/png"),
        ]
    )
    (image,) = result_images(result)
    assert (image.data, image.mime_type, image.width, image.height) == (
        PNG_BYTES,
        "image/png",
        PNG_WIDTH,
        PNG_HEIGHT,
    )


def test_a_result_of_text_alone_carries_no_images() -> None:
    assert result_images(CallToolResult(content=[TextContent(type="text", text="x")])) == ()


def test_every_image_block_is_read_in_wire_order() -> None:
    first, second = _block(PNG_BYTES), _block(_resized(4, 5))
    images = result_images(CallToolResult(content=[first, second]))
    assert [(i.width, i.height) for i in images] == [(PNG_WIDTH, PNG_HEIGHT), (4, 5)]


def test_a_block_whose_data_is_not_base64_is_refused() -> None:
    block = ImageContent(type="image", data="not base64", mimeType="image/png")
    with pytest.raises(ImageError, match="not valid base64"):
        result_images(CallToolResult(content=[block]))


def test_a_block_carrying_a_character_outside_the_base64_alphabet_is_refused() -> None:
    # `b64decode` discards an unknown character unless it is validating, so a decoder without
    # `validate=True` would read this as the PNG and never report the byte that was thrown away.
    block = ImageContent(type="image", data=PNG_BASE64 + "!", mimeType="image/png")
    with pytest.raises(ImageError, match="not valid base64"):
        result_images(CallToolResult(content=[block]))


@pytest.mark.parametrize(
    ("data", "mime"), [(JPEG_BYTES, "image/jpeg"), (LOSSY_WEBP_BYTES, "image/webp")]
)
def test_a_block_in_either_other_listed_format_is_carried(data: bytes, mime: str) -> None:
    (image,) = result_images(CallToolResult(content=[_block(data, mime)]))
    assert (image.mime_type, image.width, image.height) == (mime, SAMPLE_WIDTH, SAMPLE_HEIGHT)


def test_a_block_in_a_format_with_no_reader_is_refused() -> None:
    # A GIF states its size in a header nothing here reads, so it fails closed rather than
    # arriving at a guessed size.
    with pytest.raises(ImageError, match="not a PNG, JPEG or WebP"):
        result_images(CallToolResult(content=[_block(b"GIF89a" + b"0" * 40, "image/gif")]))


def test_a_png_too_short_to_hold_a_header_is_refused() -> None:
    with pytest.raises(ImageError, match="too few to carry a PNG header"):
        result_images(CallToolResult(content=[_block(PNG_BYTES[:20])]))


def test_a_header_stating_a_size_past_the_core_bound_is_refused() -> None:
    # The size is a declaration like any other, so the core's edge bound still judges it.
    with pytest.raises(ImageError, match=f"outside 1..{MAX_IMAGE_EDGE}"):
        result_images(CallToolResult(content=[_block(_resized(MAX_IMAGE_EDGE + 1, 1))]))


def test_a_png_declared_under_an_unlisted_mime_type_is_refused() -> None:
    # The mime type is the sidecar's word and the core's allow-list judges it, exactly as it
    # judges the body's declared type.
    with pytest.raises(ImageError, match="unsupported image type 'image/gif'"):
        result_images(CallToolResult(content=[_block(PNG_BYTES, "image/gif")]))
