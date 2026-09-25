"""Read the images a ``UserTurn`` brings over the wire into checked core image parts."""

from collections.abc import Sequence

from cortex_core import AttachmentError, ImageError, ImagePart, check_attachments
from cortex_seam import ImageBlob

ERROR_CODE_ATTACHMENT_REFUSED = "attachment_refused"


def read_attachments(blobs: Sequence[ImageBlob]) -> tuple[ImagePart, ...]:
    """The turn's attachments as image parts; raise ``AttachmentError`` for one it refuses."""
    parts: list[ImagePart] = []
    for index, blob in enumerate(blobs, start=1):
        try:
            parts.append(
                ImagePart(
                    data=blob.data, mime_type=blob.mime_type, width=blob.width, height=blob.height
                )
            )
        except ImageError as err:
            msg = f"attachment {index} was refused: {err}"
            raise AttachmentError(msg) from err
    return check_attachments(parts)
