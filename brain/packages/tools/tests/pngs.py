"""One real PNG, shared by every test that needs an MCP image block to carry something."""

import base64

PNG_WIDTH = 2
PNG_HEIGHT = 3
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAEElEQVR4nGP4z8AARAwo"
    "FABE0AX7pM/egAAAAABJRU5ErkJggg=="
)
PNG_BYTES = base64.b64decode(PNG_BASE64)
