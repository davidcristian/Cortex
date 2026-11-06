# A request to remember that names a photo keeps the file tools

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-11-06

`_SOURCE` (`unasked_tools.py`) lists `photos?`, `pictures?` and `images?` as source words, so
`Remember my resume needs a new photo` keeps the file tools on a request that states a fact and names
no file. The 2026-10-31 W01 draws show the price of a wrong keep: a file call keeps the turn out of
memory, so the fact is lost
([readings](../../readings/sidecar-tools-record-words.md#the-reader-2026-11-06)). The message was
written as a near miss for the record-word reader and turned out to be kept already.

## What to do

Decide, with near misses as tests first and a replay of every recorded message, whether a picture word
needs a source shape (`the photo in my ...`, `my photos folder`) the way a record word now does, or
stays a plain source word. Draw a rule written first; the W01 price says a wrong keep is the side to
avoid.

## History

- 2026-11-06: filed while rebuilding the record-word reader (task 972).
- 2026-11-06: premise checked in the fix slot after the closing audit. `_SOURCE` keeps the file
  tools on every message naming a photo, the stated facts (`Remember that the photo of grandma
  is in the hallway`, `Note that the image on my badge is old`) and the real requests (`Remember
  the photo in Downloads`, `Remember the picture I sent you`, `Remember the picture of the
  whiteboard`) alike. A fact shape over a form of "to be" alone does not reach the resume
  message, and a location clause (`on my badge`, `from the trip`) names a fact as often as a
  file, so the source shape must cover the sent, attached and folder forms and the fact shape
  the rest. Left open for a slot with time to draw the near misses on a rule written first.
