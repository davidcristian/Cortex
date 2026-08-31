"""Image parts: the only way pixels are represented anywhere in the brain."""

import base64
from dataclasses import dataclass

# 6 MiB, the same as the body's MAX_CAPTURE_BYTES: a worst-case incompressible screen encodes
# to 4.33 MB at the body's 1600 px default edge, so a tighter bound would reject real screens.
MAX_IMAGE_BYTES = 6 * 1024 * 1024

# Well above anything the capture path produces, since the body clamps at 4096. Width and
# height are declared metadata the core never checks against the bytes, so this only rejects
# a nonsense declaration.
MAX_IMAGE_EDGE = 8192

ALLOWED_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


class ImageError(ValueError):
    """An image part that cannot be built: empty, unlisted mime, bad size, or too many bytes."""


@dataclass(frozen=True, slots=True)
class ImagePart:
    """One encoded image, validated at construction and immutable after it."""

    data: bytes
    mime_type: str
    width: int
    height: int

    def __post_init__(self) -> None:
        """Reject anything that is not a plausible, in-budget image."""
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
    """Render ``part`` as a ``data:`` URI, the form an OpenAI content-parts array takes."""
    encoded = base64.b64encode(part.data).decode("ascii")
    return f"data:{part.mime_type};base64,{encoded}"
