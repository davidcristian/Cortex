"""One real picture per container shape `cortex_tools.headers` reads, shared by every test.

Genuine encoder output rather than fabricated headers, so each reader is proven against bytes an
encoder produced. The PNG is 2 by 3 and the four later pictures are 4 by 6; both sizes have two
different edges, so a reader that returned them the wrong way round fails. Regenerate the PNG with:

    python -c "import zlib,struct,base64
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''.join(b'\\x00' + b'\\xff\\x00\\x00' * 2 for _ in range(3))
    png = (b'\\x89PNG\\r\\n\\x1a\\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 3, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    print(base64.b64encode(png).decode())"

and the other four with ffmpeg, one command each, base64 of the file it writes:

    ffmpeg -f lavfi -i color=red:s=4x6 -frames:v 1 -pix_fmt yuvj420p a.jpg
    ffmpeg -f lavfi -i color=red:s=4x6 -frames:v 1 -c:v libwebp -lossless 0 -pix_fmt yuv420p b.webp
    ffmpeg -f lavfi -i color=red:s=4x6 -frames:v 1 -c:v libwebp -lossless 1 -pix_fmt bgra c.webp
    ffmpeg -f lavfi -i "color=red@0.5:s=4x6,format=rgba" -frames:v 1 -pix_fmt yuva420p d.webp

The last command asks for an alpha channel, which is what makes libwebp write the extended VP8X
container rather than a bare VP8 chunk.
"""

import base64

PNG_WIDTH = 2
PNG_HEIGHT = 3
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAEElEQVR4nGP4z8AARAwo"
    "FABE0AX7pM/egAAAAABJRU5ErkJggg=="
)
PNG_BYTES = base64.b64decode(PNG_BASE64)

# The size every picture below carries, stated once because all four encoders were asked for it.
SAMPLE_WIDTH = 4
SAMPLE_HEIGHT = 6

_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAgAAAQABAAD//gAQTGF2YzYwLjMxLjEwMgD/2wBDAAgEBAQEBAUFBQUFBQYGBgYGBgYG"
    "BgYGBgYHBwcICAgHBwcGBgcHCAgICAkJCQgICAgJCQoKCgwMCwsODg4RERT/xABMAAEBAAAAAAAAAAAAAAAA"
    "AAAABgEBAQAAAAAAAAAAAAAAAAAABgcQAQAAAAAAAAAAAAAAAAAAAAARAQAAAAAAAAAAAAAAAAAAAAD/wAAR"
    "CAAGAAQDASIAAhEAAxEA/9oADAMBAAIRAxEAPwCLAFF/f//Z"
)
_LOSSY_BASE64 = (
    "UklGRjwAAABXRUJQVlA4IDAAAADQAQCdASoEAAYAAgA0JaACdLoB+AADsAD+8Oj3/yC5YXXI1/8gP+QH/ID/+PIAAAA="
)
_LOSSLESS_BASE64 = "UklGRiAAAABXRUJQVlA4TBQAAAAvA0ABAAcQ7Y/+BwCC8L9tIqL/IQ=="
_EXTENDED_BASE64 = (
    "UklGRmYAAABXRUJQVlA4WAoAAAAQAAAAAwAABQAAQUxQSA8AAAABB9C/iAgABOF/20RE/0MAVlA4IDAAAADQ"
    "AQCdASoEAAYAAgA0JaACdLoB+AADsAD+8Oj3/yC5YXXI1/8gP+QH/ID/+PIAAAA="
)

# A baseline JPEG whose segment chain runs APP0, COM, DQT, DHT and then SOF0, so the walk that
# finds the frame header steps over four segments, one of them the DHT marker that sits inside the
# 0xC0 to 0xCF range without being a frame header.
JPEG_BYTES = base64.b64decode(_JPEG_BASE64)
# The three WebP container shapes: a bare lossy keyframe, a lossless bitstream, and the extended
# container an alpha channel forces, which states the canvas size itself and carries the picture in
# later chunks.
LOSSY_WEBP_BYTES = base64.b64decode(_LOSSY_BASE64)
LOSSLESS_WEBP_BYTES = base64.b64decode(_LOSSLESS_BASE64)
EXTENDED_WEBP_BYTES = base64.b64decode(_EXTENDED_BASE64)
