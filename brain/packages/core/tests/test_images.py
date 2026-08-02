"""Behavioural tests for cortex_core.images (ADR-0029): every reject branch of ``ImagePart``,
the ``data_uri`` rendering, and the two bounds pinned against their literals.

The bounds are pinned to numbers rather than to each other because they are half of a ceiling
the body enforces in another language: a test that only asserted ``MAX_IMAGE_BYTES ==
MAX_IMAGE_BYTES`` would stay green while the two halves of the seam drifted apart. This pin
catches an edit to the constant alone; an edit to the constant *and* this literal is what
``scripts/crosscheck.py`` catches, since no suite here can read the body's Rust.
"""

import base64

import pytest

from cortex_core import (
    ALLOWED_MIME_TYPES,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_EDGE,
    ImageError,
    ImagePart,
    data_uri,
)

_PNG = b"\x89PNG\r\n\x1a\n"


def test_the_byte_budget_is_six_mebibytes() -> None:
    # The body's MAX_CAPTURE_BYTES is the same number in Rust. Each side pins the literal, the
    # brain sends this value as the request's max_bytes, and crosscheck.py ties the two.
    assert MAX_IMAGE_BYTES == 6291456
    assert MAX_IMAGE_EDGE == 8192


def test_the_allowed_types_are_the_three_lossless_and_lossy_web_encodings() -> None:
    assert frozenset({"image/png", "image/jpeg", "image/webp"}) == ALLOWED_MIME_TYPES


def test_a_valid_part_keeps_what_it_was_given() -> None:
    part = ImagePart(data=_PNG, mime_type="image/png", width=1600, height=900)
    assert part.data == _PNG
    assert (part.width, part.height) == (1600, 900)


def test_an_empty_part_is_refused() -> None:
    with pytest.raises(ImageError, match="an image part carries no bytes"):
        ImagePart(data=b"", mime_type="image/png", width=4, height=4)


def test_an_unlisted_mime_is_refused() -> None:
    with pytest.raises(ImageError, match="unsupported image type 'image/svg\\+xml'"):
        ImagePart(data=_PNG, mime_type="image/svg+xml", width=4, height=4)


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (0, 4, "image width 0 is outside 1..8192"),
        (-1, 4, "image width -1 is outside 1..8192"),
        (8193, 4, "image width 8193 is outside 1..8192"),
        (4, 0, "image height 0 is outside 1..8192"),
        (4, 8193, "image height 8193 is outside 1..8192"),
    ],
)
def test_an_impossible_dimension_is_refused(width: int, height: int, expected: str) -> None:
    with pytest.raises(ImageError, match=expected):
        ImagePart(data=_PNG, mime_type="image/png", width=width, height=height)


def test_a_dimension_at_the_edge_of_the_bound_is_accepted() -> None:
    part = ImagePart(data=_PNG, mime_type="image/png", width=MAX_IMAGE_EDGE, height=1)
    assert part.width == 8192


def test_an_over_budget_part_is_refused_with_a_message_naming_both_numbers() -> None:
    oversized = b"\x00" * (MAX_IMAGE_BYTES + 1)
    with pytest.raises(ImageError, match="image is 6291457 bytes, over the 6291456 byte budget"):
        ImagePart(data=oversized, mime_type="image/png", width=4, height=4)


def test_a_part_exactly_at_the_budget_is_accepted() -> None:
    part = ImagePart(data=b"\x00" * MAX_IMAGE_BYTES, mime_type="image/png", width=4, height=4)
    assert len(part.data) == MAX_IMAGE_BYTES


def test_data_uri_renders_the_form_the_inference_payload_takes() -> None:
    part = ImagePart(data=_PNG, mime_type="image/png", width=4, height=4)
    assert data_uri(part) == "data:image/png;base64,iVBORw0KGgo="
    # Independently: the tail really is standard base64 of the bytes, not a lookalike.
    assert base64.b64decode(data_uri(part).split(",", 1)[1]) == _PNG


def test_data_uri_names_the_declared_type_rather_than_assuming_png() -> None:
    part = ImagePart(data=_PNG, mime_type="image/webp", width=4, height=4)
    assert data_uri(part).startswith("data:image/webp;base64,")
