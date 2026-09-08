"""The width and height an encoded image's container header states (ADR-0009).

An MCP `ImageContent` block states no dimensions and `ImagePart` requires them, so the size is read
out of the bytes. One reader per format the core's `ALLOWED_MIME_TYPES` lists: PNG's IHDR chunk, a
JPEG's first frame header, and the first chunk of a WebP RIFF container, which states the size in
one of three shapes. A block carrying none of the three signatures raises `ImageError`.

Nothing here is a decode. No pixel, entropy-coded byte, or palette is read, so the posture
`cortex_core.images` sets out, that no attacker-controlled bytes reach a decoder inside the process
holding the durable memory store, still holds with this module in it. PNG and WebP are fixed-offset
reads. JPEG is not: its frame header sits behind a chain of segments whose lengths the bytes
themselves state, so finding it means following a length an attacker wrote. That walk is bounded
three ways, argued in the ADR-0009 sized-formats addendum. It takes at most `MAX_JPEG_SEGMENTS`
steps; every segment must state a length of at least two bytes, so the cursor advances every step;
and every offset is compared against the buffer before it is read. A truncated chain, a length
running past the end, and a chain that reaches the scan data without a frame header all raise
`ImageError` rather than looping, reading past the end, or raising `struct.error`.
"""

import struct
from collections.abc import Callable

from cortex_core.images import ImageError

# PNG states its dimensions in the IHDR chunk, which the format requires first: an 8 byte
# signature, the chunk's 4 byte length and 4 byte type, then width and height as big-endian
# unsigned 32 bit integers at bytes 16 to 24.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_SIZE_START = 16
_PNG_SIZE_END = 24

# JPEG opens with SOI and then a chain of segments, each introduced by a 0xFF byte and a one byte
# marker code. Most carry a two byte big-endian length that counts itself, and the size is stated
# by the first frame header the chain reaches.
_JPEG_SIGNATURE = b"\xff\xd8"
_MARKER_PREFIX = 0xFF
_LENGTH_BYTES = 2
# TEM and the eight restart markers carry no length and no payload, and neither does a repeated SOI.
_STANDALONE_MARKERS = frozenset({0x01, *range(0xD0, 0xD9)})
# EOI and SOS. Either one ends the useful chain: entropy-coded bytes follow a scan header, and a
# reader that walked into them would be reading compressed pixels.
_CHAIN_ENDS = frozenset({0xD9, 0xDA})
# SOF0 through SOF15, less the three codes in that range the format assigns to other tables:
# DHT (0xC4), the reserved JPG marker (0xC8), and DAC (0xCC).
_SOF_MARKERS = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
# A frame header states one byte of sample precision and then height and width, so its size sits at
# bytes 3 to 7 of the segment, counting from the length field.
_SOF_SIZE_START = 3
_SOF_SIZE_END = 7

# The most segments the walk steps through before it gives up. Far above any real file: an ICC
# profile alone may be split across 255 APP2 segments, and everything else an encoder writes ahead
# of the frame header is counted in tens.
MAX_JPEG_SEGMENTS = 512

# WebP is a RIFF container: the "RIFF" tag, a four byte little-endian file size, the "WEBP" form
# name, and then chunks, each a four byte name and a four byte little-endian payload length. The
# canvas size is stated by the first chunk, whichever of the three shapes it is.
_WEBP_SIGNATURE = b"RIFF"
_WEBP_FORM = b"WEBP"
_WEBP_FORM_START = 8
_WEBP_FORM_END = 12
_WEBP_NAME_START = 12
_WEBP_NAME_END = 16
_WEBP_PAYLOAD_START = 20

# A lossy VP8 keyframe states its size after a three byte frame tag and a three byte sync code, as
# two little-endian 16 bit fields of which the low 14 bits are the edge and the high 2 the scale.
_VP8_SYNC = b"\x9d\x01\x2a"
_VP8_SYNC_START = 3
_VP8_SYNC_END = 6
_VP8_SIZE_END = 10
_VP8_EDGE_MASK = 0x3FFF

# A lossless VP8L header is a signature byte and then four little-endian bytes carrying width minus
# one in the low 14 bits and height minus one in the next 14.
_VP8L_SIGNATURE = 0x2F
_VP8L_BITS_START = 1
_VP8L_BITS_END = 5
_VP8L_EDGE_BITS = 14
_VP8L_EDGE_MASK = (1 << _VP8L_EDGE_BITS) - 1

# An extended VP8X chunk states the canvas size after four bytes of flags, as two little-endian
# 24 bit fields, each one less than the edge it names.
_VP8X_WIDTH_START = 4
_VP8X_HEIGHT_START = 7
_VP8X_SIZE_END = 10


def _png_size(data: bytes) -> tuple[int, int]:
    """The width and height PNG's IHDR chunk states."""
    if len(data) < _PNG_SIZE_END:
        msg = f"an MCP image block is {len(data)} bytes, too few to carry a PNG header"
        raise ImageError(msg)
    width, height = struct.unpack(">II", data[_PNG_SIZE_START:_PNG_SIZE_END])
    return width, height


def _jpeg_marker(data: bytes, pos: int) -> tuple[int, int]:
    """The marker code at ``pos`` and the offset just past it, skipping the fill bytes before it."""
    if pos >= len(data):
        msg = "a JPEG image block ends before its segments reach a frame header"
        raise ImageError(msg)
    if data[pos] != _MARKER_PREFIX:
        msg = f"a JPEG image block holds {data[pos]:#04x} where a segment marker must begin"
        raise ImageError(msg)
    # A marker may be preceded by any number of 0xFF fill bytes, so the marker code is the first
    # byte after that run rather than the byte after the first 0xFF.
    while pos < len(data) and data[pos] == _MARKER_PREFIX:
        pos += 1
    if pos >= len(data):
        msg = "a JPEG image block ends inside a run of segment padding"
        raise ImageError(msg)
    return data[pos], pos + 1


def _segment_length(data: bytes, pos: int) -> int:
    """The length a segment states, refused unless it advances the walk and fits in the block."""
    if pos + _LENGTH_BYTES > len(data):
        msg = "a JPEG image block ends inside a segment length"
        raise ImageError(msg)
    (length,) = struct.unpack(">H", data[pos : pos + _LENGTH_BYTES])
    if length < _LENGTH_BYTES:
        msg = f"a JPEG segment states a length of {length}, which would not advance the walk"
        raise ImageError(msg)
    if pos + length > len(data):
        msg = f"a JPEG segment states a length of {length}, running past the end of the block"
        raise ImageError(msg)
    return length


def _frame_size(data: bytes, pos: int, length: int) -> tuple[int, int]:
    """The width and height a frame header states, which JPEG writes height first."""
    if length < _SOF_SIZE_END:
        msg = f"a JPEG frame header is {length} bytes, too few to state a size"
        raise ImageError(msg)
    height, width = struct.unpack(">HH", data[pos + _SOF_SIZE_START : pos + _SOF_SIZE_END])
    return width, height


def _jpeg_size(data: bytes) -> tuple[int, int]:
    """The size the first frame header states, walking the bounded segment chain to reach it."""
    pos = len(_JPEG_SIGNATURE)
    for _ in range(MAX_JPEG_SEGMENTS):
        marker, pos = _jpeg_marker(data, pos)
        if marker in _STANDALONE_MARKERS:
            continue
        if marker in _CHAIN_ENDS:
            msg = "a JPEG image block reaches its scan data with no frame header before it"
            raise ImageError(msg)
        length = _segment_length(data, pos)
        if marker in _SOF_MARKERS:
            return _frame_size(data, pos, length)
        pos += length
    msg = f"a JPEG image block states no size in its first {MAX_JPEG_SEGMENTS} segments"
    raise ImageError(msg)


def _vp8_size(payload: bytes) -> tuple[int, int]:
    """The size a lossy VP8 keyframe states, 14 bits of each edge behind a sync code."""
    if len(payload) < _VP8_SIZE_END:
        msg = "a WebP image block is too short to carry a lossy keyframe header"
        raise ImageError(msg)
    if payload[_VP8_SYNC_START:_VP8_SYNC_END] != _VP8_SYNC:
        msg = "a WebP lossy chunk does not carry the keyframe sync code"
        raise ImageError(msg)
    width, height = struct.unpack("<HH", payload[_VP8_SYNC_END:_VP8_SIZE_END])
    return width & _VP8_EDGE_MASK, height & _VP8_EDGE_MASK


def _vp8l_size(payload: bytes) -> tuple[int, int]:
    """The size a lossless VP8L header states, two 14 bit fields packed across four bytes."""
    if len(payload) < _VP8L_BITS_END:
        msg = "a WebP image block is too short to carry a lossless header"
        raise ImageError(msg)
    if payload[0] != _VP8L_SIGNATURE:
        msg = "a WebP lossless chunk does not open with its signature byte"
        raise ImageError(msg)
    (bits,) = struct.unpack("<I", payload[_VP8L_BITS_START:_VP8L_BITS_END])
    width = (bits & _VP8L_EDGE_MASK) + 1
    height = ((bits >> _VP8L_EDGE_BITS) & _VP8L_EDGE_MASK) + 1
    return width, height


def _vp8x_size(payload: bytes) -> tuple[int, int]:
    """The canvas size an extended VP8X chunk states, as two little-endian 24 bit fields."""
    if len(payload) < _VP8X_SIZE_END:
        msg = "a WebP image block is too short to carry an extended canvas header"
        raise ImageError(msg)
    width = int.from_bytes(payload[_VP8X_WIDTH_START:_VP8X_HEIGHT_START], "little") + 1
    height = int.from_bytes(payload[_VP8X_HEIGHT_START:_VP8X_SIZE_END], "little") + 1
    return width, height


_WEBP_SHAPES: dict[bytes, Callable[[bytes], tuple[int, int]]] = {
    b"VP8 ": _vp8_size,
    b"VP8L": _vp8l_size,
    b"VP8X": _vp8x_size,
}


def _webp_size(data: bytes) -> tuple[int, int]:
    """The canvas size the container's first chunk states, in whichever shape that chunk is."""
    if len(data) < _WEBP_PAYLOAD_START:
        msg = f"an MCP image block is {len(data)} bytes, too few to carry a WebP header"
        raise ImageError(msg)
    if data[_WEBP_FORM_START:_WEBP_FORM_END] != _WEBP_FORM:
        msg = "a RIFF image block does not name WEBP as its form"
        raise ImageError(msg)
    name = data[_WEBP_NAME_START:_WEBP_NAME_END]
    shape = _WEBP_SHAPES.get(name)
    if shape is None:
        msg = f"a WebP image block opens with the {name!r} chunk, which states no canvas size"
        raise ImageError(msg)
    return shape(data[_WEBP_PAYLOAD_START:])


_READERS: tuple[tuple[bytes, Callable[[bytes], tuple[int, int]]], ...] = (
    (_PNG_SIGNATURE, _png_size),
    (_JPEG_SIGNATURE, _jpeg_size),
    (_WEBP_SIGNATURE, _webp_size),
)


def image_size(data: bytes) -> tuple[int, int]:
    """The width and height ``data``'s container states; ``ImageError`` when no reader claims it."""
    for signature, reader in _READERS:
        if data.startswith(signature):
            return reader(data)
    msg = "an MCP image block is not a PNG, JPEG or WebP, the formats whose size this reads"
    raise ImageError(msg)
