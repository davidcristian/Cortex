"""Behavior tests for the image-header readers (`cortex_tools.headers`, ADR-0009).

The readers state the width and height an encoded image's container declares, for the three
formats the core's `ALLOWED_MIME_TYPES` lists. Every picture read here is real encoder output
(`pictures.py`); every refusal is built byte by byte, because a malformed container is exactly what
an encoder will not produce. The JPEG walk is the reason most of these exist: it follows lengths
the bytes themselves state, so each way that chain can lie has a test.
"""

import struct

import pytest
from pictures import (
    EXTENDED_WEBP_BYTES,
    JPEG_BYTES,
    LOSSLESS_WEBP_BYTES,
    LOSSY_WEBP_BYTES,
    SAMPLE_HEIGHT,
    SAMPLE_WIDTH,
)

from cortex_core.images import ImageError
from cortex_tools.headers import MAX_JPEG_SEGMENTS, image_size

SOI = b"\xff\xd8"
SAMPLE_SIZE = (SAMPLE_WIDTH, SAMPLE_HEIGHT)
# The bit a lossless header sets to announce an alpha channel, just above the two packed edges.
VP8L_ALPHA_BIT = 1 << 28


def _segment(marker: int, payload: bytes = b"") -> bytes:
    """One length-bearing JPEG segment: the marker, a length counting itself, then the payload."""
    return bytes((0xFF, marker)) + struct.pack(">H", len(payload) + 2) + payload


def test_a_jpeg_is_read_at_the_size_its_frame_header_states() -> None:
    # The shared JPEG's chain runs APP0, COM, DQT, DHT, SOF0, so this also holds that DHT (0xC4)
    # is not read as a frame header despite sitting inside the 0xC0 to 0xCF marker range.
    assert image_size(JPEG_BYTES) == SAMPLE_SIZE


def test_a_jpeg_walk_steps_over_a_marker_that_carries_no_length() -> None:
    assert image_size(SOI + b"\xff\x01" + JPEG_BYTES[2:]) == SAMPLE_SIZE


def test_a_jpeg_walk_steps_over_the_fill_bytes_before_a_marker() -> None:
    # A marker may be preceded by any number of 0xFF fill bytes, so the code is the first byte
    # after the run rather than the byte after the first 0xFF.
    assert image_size(SOI + b"\xff\xff\xff\x01" + JPEG_BYTES[2:]) == SAMPLE_SIZE


def test_a_jpeg_ending_before_its_segments_reach_a_frame_header_is_refused() -> None:
    with pytest.raises(ImageError, match="ends before its segments reach a frame header"):
        image_size(SOI)


def test_a_jpeg_holding_a_byte_where_a_marker_must_begin_is_refused() -> None:
    with pytest.raises(ImageError, match="holds 0x00 where a segment marker must begin"):
        image_size(SOI + b"\x00\x00")


def test_a_jpeg_ending_in_marker_padding_is_refused() -> None:
    with pytest.raises(ImageError, match="ends inside a run of segment padding"):
        image_size(SOI + b"\xff\xff")


def test_a_jpeg_ending_inside_a_segment_length_is_refused() -> None:
    with pytest.raises(ImageError, match="ends inside a segment length"):
        image_size(SOI + b"\xff\xe0\x00")


def test_a_jpeg_segment_length_that_cannot_advance_the_walk_is_refused() -> None:
    # A length of 1 counts fewer bytes than the length field itself, so a walk that trusted it
    # would read the same two bytes forever.
    with pytest.raises(ImageError, match="length of 1, which would not advance the walk"):
        image_size(SOI + b"\xff\xe0\x00\x01")


def test_a_jpeg_segment_length_running_past_the_end_is_refused() -> None:
    with pytest.raises(ImageError, match="length of 65535, running past the end"):
        image_size(SOI + b"\xff\xe0\xff\xff")


@pytest.mark.parametrize("ending", [b"\xff\xd9", b"\xff\xda"])
def test_a_jpeg_reaching_the_end_of_its_chain_without_a_size_is_refused(ending: bytes) -> None:
    # End of image and start of scan both end the useful chain: a reader that walked past a scan
    # header would be reading entropy-coded pixels.
    with pytest.raises(ImageError, match="scan data with no frame header before it"):
        image_size(SOI + ending)


def test_a_jpeg_frame_header_length_running_past_the_end_is_refused() -> None:
    # The same lie told by a frame header rather than by a segment the walk skips. Without the
    # length check the short slice behind it would raise `struct.error` instead of `ImageError`.
    with pytest.raises(ImageError, match="length of 17, running past the end"):
        image_size(SOI + b"\xff\xc0\x00\x11\x08\x00\x06")


def test_a_jpeg_frame_header_too_short_to_state_a_size_is_refused() -> None:
    with pytest.raises(ImageError, match="frame header is 3 bytes, too few to state a size"):
        image_size(SOI + _segment(0xC0, b"\x08"))


def test_a_jpeg_chain_longer_than_the_walk_allows_is_refused() -> None:
    chain = SOI + _segment(0xE0) * (MAX_JPEG_SEGMENTS + 1)
    with pytest.raises(ImageError, match=f"no size in its first {MAX_JPEG_SEGMENTS} segments"):
        image_size(chain)


def test_a_lossy_webp_is_read_at_the_size_its_keyframe_states() -> None:
    assert image_size(LOSSY_WEBP_BYTES) == SAMPLE_SIZE


def test_a_lossless_webp_is_read_at_the_size_packed_into_its_header() -> None:
    assert image_size(LOSSLESS_WEBP_BYTES) == SAMPLE_SIZE


def test_an_extended_webp_is_read_at_the_canvas_size_it_states() -> None:
    assert image_size(EXTENDED_WEBP_BYTES) == SAMPLE_SIZE


def test_a_lossy_webp_edge_is_read_without_the_scale_bits_above_it() -> None:
    # The top two bits of each 16 bit field are a scale factor rather than part of the edge. No
    # encoder here sets them, so a keyframe that does is built by hand from the shared picture.
    scaled = struct.pack("<HH", SAMPLE_WIDTH | 0xC000, SAMPLE_HEIGHT | 0x8000)
    assert image_size(LOSSY_WEBP_BYTES[:26] + scaled + LOSSY_WEBP_BYTES[30:]) == SAMPLE_SIZE


def test_a_lossless_webp_edge_is_read_without_the_flags_above_it() -> None:
    # The four bits above the two packed edges are the alpha flag and a three bit version, so a
    # header that announces alpha still states the same picture size.
    (bits,) = struct.unpack("<I", LOSSLESS_WEBP_BYTES[21:25])
    flagged = struct.pack("<I", bits | VP8L_ALPHA_BIT)
    assert image_size(LOSSLESS_WEBP_BYTES[:21] + flagged + LOSSLESS_WEBP_BYTES[25:]) == SAMPLE_SIZE


def test_a_riff_block_too_short_to_carry_a_webp_header_is_refused() -> None:
    with pytest.raises(ImageError, match="19 bytes, too few to carry a WebP header"):
        image_size(LOSSY_WEBP_BYTES[:19])


def test_a_riff_block_naming_another_form_is_refused() -> None:
    with pytest.raises(ImageError, match="does not name WEBP as its form"):
        image_size(LOSSY_WEBP_BYTES[:8] + b"AVI " + LOSSY_WEBP_BYTES[12:])


def test_a_webp_opening_with_a_chunk_that_states_no_size_is_refused() -> None:
    # ALPH is a real WebP chunk, and a container that opens with one is malformed: the extended
    # header stating the canvas size has to come first.
    with pytest.raises(ImageError, match="opens with the b'ALPH' chunk"):
        image_size(LOSSY_WEBP_BYTES[:12] + b"ALPH" + LOSSY_WEBP_BYTES[16:])


def test_a_lossy_webp_too_short_for_its_keyframe_header_is_refused() -> None:
    with pytest.raises(ImageError, match="too short to carry a lossy keyframe header"):
        image_size(LOSSY_WEBP_BYTES[:29])


def test_a_lossy_webp_without_the_keyframe_sync_code_is_refused() -> None:
    with pytest.raises(ImageError, match="does not carry the keyframe sync code"):
        image_size(LOSSY_WEBP_BYTES[:23] + b"\x00\x00\x00" + LOSSY_WEBP_BYTES[26:])


def test_a_lossless_webp_too_short_for_its_header_is_refused() -> None:
    with pytest.raises(ImageError, match="too short to carry a lossless header"):
        image_size(LOSSLESS_WEBP_BYTES[:24])


def test_a_lossless_webp_without_its_signature_byte_is_refused() -> None:
    with pytest.raises(ImageError, match="does not open with its signature byte"):
        image_size(LOSSLESS_WEBP_BYTES[:20] + b"\x00" + LOSSLESS_WEBP_BYTES[21:])


def test_an_extended_webp_too_short_for_its_canvas_header_is_refused() -> None:
    with pytest.raises(ImageError, match="too short to carry an extended canvas header"):
        image_size(EXTENDED_WEBP_BYTES[:29])


def test_a_block_in_a_format_no_reader_claims_is_refused() -> None:
    with pytest.raises(ImageError, match="not a PNG, JPEG or WebP"):
        image_size(b"GIF89a" + b"\x00" * 20)
