"""One real PNG, shared by every test that needs an MCP image block to carry something.

A genuine 2 by 3 pixel PNG rather than a fabricated header, so the reader in
`cortex_tools.blocks` is proven against bytes an encoder produced. Regenerate with:

    python -c "import zlib,struct,base64
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''.join(b'\\x00' + b'\\xff\\x00\\x00' * 2 for _ in range(3))
    png = (b'\\x89PNG\\r\\n\\x1a\\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 3, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    print(base64.b64encode(png).decode())"
"""

import base64

PNG_WIDTH = 2
PNG_HEIGHT = 3
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAEElEQVR4nGP4z8AARAwo"
    "FABE0AX7pM/egAAAAABJRU5ErkJggg=="
)
PNG_BYTES = base64.b64decode(PNG_BASE64)
