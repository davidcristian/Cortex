"""A 4K painter and a transcription of the body's own crop and downscale (ADR-0029).

Two halves of one job: draw a synthetic desktop at real physical type sizes, then put it
through the arithmetic ``body_core`` would put a real capture through, so the picture a
legibility measurement scores is the picture the seam would actually carry.

**The painter is antialiased, which the injection corpus's is not.** That corpus draws a
5x8 bitmap font at integer scale, so its smallest text has 1 px strokes and a 7 px cap
height, and nothing between that and 14 px. A legibility measurement is about the sizes in
between: 15 px type has an 11 px cap and roughly 1.5 px strokes, which an integer-scaled
bitmap cannot express at all. So every string is rasterised at six times its final size and
box-filtered down, which is what a hinting-free FreeType render does to the same shapes, and
the result is grey-edged text whose stroke weight tracks the type size. Standard library
only and deterministic, for the reasons [pixel_font.py](pixel_font.py) gives.

**The pipeline half is a transcription, not a port.** ``scaled_dimensions``, the identity arm
and ``box_filter`` are read off ``body/crates/core/src/os/screen_image.rs`` and rewritten
here, integer floor for integer floor, including the crop that the same file's ``downscale``
now takes as a ``Region``. The one deliberate difference is the pixel order: the Rust reads
BGRA frames and drops the undefined fourth byte, this reads RGB, which changes no arithmetic
because every channel is averaged independently.
"""

import struct
import zlib
from dataclasses import dataclass

from pixel_font import GLYPH_HEIGHT, GLYPH_WIDTH, glyph

Colour = tuple[int, int, int]

# How many source pixels each font pixel is rasterised into before the box filter shrinks it
# to the final size. Six is enough that the smallest cap height in the corpus (11 px, from
# 15 px type) still averages over more than 50 source pixels per glyph pixel.
_SUPERSAMPLE = 6

# A real sans face puts its cap height at roughly 0.7 em, and this font spends 7 of its 8 rows
# on one. Both numbers are here so a type size in the corpus means the same thing it means on a
# desktop: 15 px type draws an 11 px cap, which is what the measured 15 px row is.
_CAP_PER_EM = 0.7
_CELL_ROWS = GLYPH_HEIGHT
_CAP_ROWS = 7
_ADVANCE_COLS = GLYPH_WIDTH + 1


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in display pixels."""

    x: int
    y: int
    width: int
    height: int

    def contains(self, other: "Rect") -> bool:
        """Whether ``other`` lies wholly inside this rectangle."""
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.x + other.width <= self.x + self.width
            and other.y + other.height <= self.y + self.height
        )


def cap_height(size: int) -> int:
    """The cap height a given physical type size draws, which is what legibility tracks.

    Rounded half up rather than by ``round``, whose half-to-even would draw 15 px type with a
    10 px cap where a real face draws 11.
    """
    return max(1, int(size * _CAP_PER_EM + 0.5))


def advance(size: int) -> int:
    """The horizontal step from one character to the next at a given type size."""
    return max(1, round(cap_height(size) * _ADVANCE_COLS / _CAP_ROWS))


class Screen:
    """An RGB pixel buffer with rectangle fills and antialiased text."""

    def __init__(self, width: int, height: int, background: Colour) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(bytes(background) * (width * height))

    def fill(self, rect: Rect, colour: Colour) -> None:
        """Fill an axis-aligned rectangle, clipped to the buffer."""
        left = max(0, rect.x)
        row = bytes(colour) * max(0, min(rect.x + rect.width, self.width) - left)
        for line in range(max(0, rect.y), min(rect.y + rect.height, self.height)):
            start = (line * self.width + left) * 3
            self.pixels[start : start + len(row)] = row

    def text(self, x: int, y: int, value: str, *, size: int, colour: Colour) -> Rect:
        """Draw ``value`` with its cell's top left at ``(x, y)`` and report the box it filled."""
        cell = max(1, round(cap_height(size) * _CELL_ROWS / _CAP_ROWS))
        width = advance(size) * len(value)
        if width == 0:
            return Rect(x, y, 0, cell)
        coverage = _shrink(_mask(value), len(value) * _ADVANCE_COLS * _SUPERSAMPLE, width, cell)
        self._blend(x, y, width, cell, coverage, colour)
        return Rect(x, y, width, cell)

    def _blend(
        self, x: int, y: int, width: int, height: int, coverage: bytes, colour: Colour
    ) -> None:
        """Composite ``colour`` over the buffer at the given coverage, one pixel at a time."""
        for row in range(height):
            line = y + row
            if not 0 <= line < self.height:
                continue
            for column in range(width):
                alpha = coverage[row * width + column]
                if alpha == 0 or not 0 <= x + column < self.width:
                    continue
                at = (line * self.width + x + column) * 3
                for channel in range(3):
                    under = self.pixels[at + channel]
                    self.pixels[at + channel] = under + (colour[channel] - under) * alpha // 255


def _mask(value: str) -> bytearray:
    """One byte per supersampled pixel, 255 where the glyphs are inked and 0 where they are not."""
    width = len(value) * _ADVANCE_COLS * _SUPERSAMPLE
    mask = bytearray(width * _CELL_ROWS * _SUPERSAMPLE)
    ink = b"\xff" * _SUPERSAMPLE
    for index, char in enumerate(value):
        left = index * _ADVANCE_COLS * _SUPERSAMPLE
        for row, bits in enumerate(glyph(char)):
            for column, bit in enumerate(bits):
                if bit != "1":
                    continue
                for line in range(_SUPERSAMPLE):
                    start = (row * _SUPERSAMPLE + line) * width + left + column * _SUPERSAMPLE
                    mask[start : start + _SUPERSAMPLE] = ink
    return mask


def _shrink(mask: bytearray, source_width: int, width: int, height: int) -> bytes:
    """Box-filter a one-byte-per-pixel mask down to ``width x height``, the same floored spans."""
    source_height = len(mask) // source_width
    out = bytearray(width * height)
    for y in range(height):
        first_row, last_row = y * source_height // height, (y + 1) * source_height // height
        for x in range(width):
            first_col, last_col = x * source_width // width, (x + 1) * source_width // width
            total = 0
            for row in range(first_row, last_row):
                total += sum(mask[row * source_width + first_col : row * source_width + last_col])
            out[y * width + x] = total // ((last_row - first_row) * (last_col - first_col))
    return bytes(out)


def scaled_dimensions(width: int, height: int, bound: int) -> tuple[int, int]:
    """``screen_image.rs``'s own: the size whose longest edge is at most ``bound``, floored."""
    longest = max(width, height)
    if longest <= bound:
        return (width, height)
    return (max(1, width * bound // longest), max(1, height * bound // longest))


def downscale(screen: Screen, region: Rect, bound: int) -> tuple[int, int, bytes]:
    """``downscale``: read ``region`` out of the frame and shrink it to ``bound``.

    The identity arm is the one the window target exists for: a region already inside the
    bound is copied pixel for pixel with no averaging at all.
    """
    width, height = scaled_dimensions(region.width, region.height, bound)
    if (width, height) == (region.width, region.height):
        return (width, height, _copy_region(screen, region))
    return (width, height, _box_filter(screen, region, width, height))


def _copy_region(screen: Screen, region: Rect) -> bytes:
    """The unscaled arm: ``region``'s own rows, in order, at full resolution."""
    out = bytearray()
    for row in range(region.height):
        start = ((region.y + row) * screen.width + region.x) * 3
        out += screen.pixels[start : start + region.width * 3]
    return bytes(out)


def _box_filter(screen: Screen, region: Rect, width: int, height: int) -> bytes:
    """Average ``region`` down to ``width x height``, every span floored as the Rust floors it."""
    pixels = screen.pixels
    stride = screen.width
    out = bytearray()
    for y in range(height):
        first_row = y * region.height // height
        last_row = (y + 1) * region.height // height
        for x in range(width):
            first_col = x * region.width // width
            last_col = (x + 1) * region.width // width
            red = green = blue = count = 0
            for row in range(first_row, last_row):
                base = ((region.y + row) * stride + region.x + first_col) * 3
                for column in range(last_col - first_col):
                    at = base + column * 3
                    red += pixels[at]
                    green += pixels[at + 1]
                    blue += pixels[at + 2]
                    count += 1
            out += bytes((red // count, green // count, blue // count))
    return bytes(out)


def encode_png(width: int, height: int, rgb: bytes) -> bytes:
    """Encode an RGB buffer as an 8-bit truecolour PNG, filter 0 on every row."""
    stride = width * 3
    raw = b"".join(b"\x00" + rgb[line * stride : (line + 1) * stride] for line in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = b"".join(
        _chunk(tag, data)
        for tag, data in ((b"IHDR", header), (b"IDAT", zlib.compress(raw, 6)), (b"IEND", b""))
    )
    return b"\x89PNG\r\n\x1a\n" + body


def _chunk(tag: bytes, data: bytes) -> bytes:
    """One length-prefixed, CRC-suffixed PNG chunk."""
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
