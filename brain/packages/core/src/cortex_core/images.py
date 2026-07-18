"""Image parts: the only way pixels are expressed anywhere in the brain (ADR-0029).

Pure data with a validating constructor, importing nothing but the standard library. That is
what lets ``tools.py``, ``conversation.py``, and ``body.py`` all depend on it without a cycle,
and it is also the security posture: **the core never decodes an image**. It checks a declared
mime against an allow-list, checks the declared size against a bound, checks the byte count,
and base64-encodes. Nothing here parses a pixel, so no attacker-controlled bytes reach a
decoder inside the process that holds the durable memory store.

The bounds are the domain half of a ceiling the body enforces too. ``MAX_IMAGE_BYTES`` is the
same 6 MiB as the body's ``MAX_CAPTURE_BYTES``, and the two must agree: a body ceiling looser
than this one would let a legitimate capture pass the body and be refused here. Nothing
mechanical couples the two constants across the language boundary, so each is pinned to the
literal in its own toolchain and the brain sends this number to the body as the request's
``max_bytes`` rather than trusting the body to hold the same constant.
"""

import base64
from dataclasses import dataclass

# The most bytes one image part may carry, 6 MiB. Matches the body's MAX_CAPTURE_BYTES: a
# worst-case incompressible screen encodes to 4.33 MB at the body's 1600 px default edge, so a
# tighter bound here would refuse ordinary photographic screens the body legitimately produced.
MAX_IMAGE_BYTES = 6 * 1024 * 1024

# The largest edge, in pixels, a declared image size may name. Far above anything the capture
# path produces (the body clamps at 4096); it exists to refuse a nonsense declaration, since
# the dimensions are metadata the core never verifies against the bytes.
MAX_IMAGE_EDGE = 8192

# The encodings an image part may declare. PNG is all the capture path emits today; JPEG and
# WebP are listed because the seam may swap the body's encoder without touching this value,
# and an allow-list that has to grow for every such change would be a second decision point.
ALLOWED_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


class ImageError(ValueError):
    """An image part that cannot be built: empty, unlisted mime, bad size, or too many bytes."""


@dataclass(frozen=True, slots=True)
class ImagePart:
    """One encoded image, validated at construction and immutable after it.

    Carried beside (never inside) a ``ToolResult``'s text, so a failed tool call can never put
    megabytes into the audit log and no fence, URL scan, or guardrail ever runs over pixels.
    """

    data: bytes
    mime_type: str
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject anything that is not a plausible, in-budget image.

        Raises ``ImageError``. The dimensions are checked as *declarations*: they say what the
        producer claims, and nothing here opens the bytes to confirm it, which is deliberate.
        """
        if not self.data:
            msg = "an image part carries no bytes"
            raise ImageError(msg)
        if self.mime_type not in ALLOWED_MIME_TYPES:
            msg = f"unsupported image type {self.mime_type!r}"
            raise ImageError(msg)
        for name, value in (("width", self.width), ("height", self.height)):
            if value <= 0 or value > MAX_IMAGE_EDGE:
                msg = f"image {name} {value} is outside 1..{MAX_IMAGE_EDGE}"
                raise ImageError(msg)
        if len(self.data) > MAX_IMAGE_BYTES:
            msg = f"image is {len(self.data)} bytes, over the {MAX_IMAGE_BYTES} byte budget"
            raise ImageError(msg)


def data_uri(part: ImagePart) -> str:
    """Render ``part`` as a ``data:`` URI, the form an OpenAI content-parts array takes.

    Standard-library base64 only. This is the whole of the brain's image processing.
    """
    encoded = base64.b64encode(part.data).decode("ascii")
    return f"data:{part.mime_type};base64,{encoded}"
