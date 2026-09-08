"""One real picture per container shape `cortex_tools.headers` reads, shared by every test."""

import base64

PNG_WIDTH = 2
PNG_HEIGHT = 3
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAEElEQVR4nGP4z8AARAwo"
    "FABE0AX7pM/egAAAAABJRU5ErkJggg=="
)
PNG_BYTES = base64.b64decode(PNG_BASE64)

# The size every picture below has, stated once because all four encoders were asked for it.
SAMPLE_WIDTH = 4
SAMPLE_HEIGHT = 6

# A baseline JPEG whose segment chain runs APP0, COM, DQT, DHT and then SOF0, so the walk that
# finds the frame header steps over four segments, one of them the DHT marker that sits inside
# the 0xC0 to 0xCF range without being a frame header.
_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAgAAAQABAAD//gAQTGF2YzYwLjMxLjEwMgD/2wBDAAgEBAQEBAUFBQUFBQYGBgYGBgYG"
    "BgYGBgYHBwcICAgHBwcGBgcHCAgICAkJCQgICAgJCQoKCgwMCwsODg4RERT/xABMAAEBAAAAAAAAAAAAAAAA"
    "AAAABgEBAQAAAAAAAAAAAAAAAAAABgcQAQAAAAAAAAAAAAAAAAAAAAARAQAAAAAAAAAAAAAAAAAAAAD/wAAR"
    "CAAGAAQDASIAAhEAAxEA/9oADAMBAAIRAxEAPwCLAFF/f//Z"
)
# The three WebP container shapes: a bare lossy keyframe, a lossless bitstream, and the
# extended container an alpha channel forces, which states the canvas size itself.
_LOSSY_BASE64 = (
    "UklGRjwAAABXRUJQVlA4IDAAAADQAQCdASoEAAYAAgA0JaACdLoB+AADsAD+8Oj3/yC5YXXI1/8gP+QH/ID/+PIAAAA="
)
_LOSSLESS_BASE64 = "UklGRiAAAABXRUJQVlA4TBQAAAAvA0ABAAcQ7Y/+BwCC8L9tIqL/IQ=="
_EXTENDED_BASE64 = (
    "UklGRmYAAABXRUJQVlA4WAoAAAAQAAAAAwAABQAAQUxQSA8AAAABB9C/iAgABOF/20RE/0MAVlA4IDAAAADQ"
    "AQCdASoEAAYAAgA0JaACdLoB+AADsAD+8Oj3/yC5YXXI1/8gP+QH/ID/+PIAAAA="
)

JPEG_BYTES = base64.b64decode(_JPEG_BASE64)
LOSSY_WEBP_BYTES = base64.b64decode(_LOSSY_BASE64)
LOSSLESS_WEBP_BYTES = base64.b64decode(_LOSSLESS_BASE64)
EXTENDED_WEBP_BYTES = base64.b64decode(_EXTENDED_BASE64)
