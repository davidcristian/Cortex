# The not found correction is undrawn on a turn that holds no listing

**Status:** done 2026-11-28
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`NOT_FOUND` tells the model to search the folder again and copy a uid from that answer. Every row
of `test_uid_reading_live.py` opens with a search, so the listing is in the turn when the
not-found answer arrives, and on the cortex tier the shipped text, the text without its correction
and the bare failure all drew the same retry with the listed uid
([cortex uid reads](../../readings/cortex-uid-reads.md)). The correction is the only path
on a turn whose read did not follow a search, such as a request that names a uid itself, and no
row draws that turn.

Closing it means a row whose first step is a read of a uid no message has, with no search before
it, drawn over the three answers of the after not found row, with its pass rule written first.

## The rule

Written 2026-11-28, before the first launch.

- **The turn.** The security preamble, the request "Read me message 1224 in my inbox, the one
  where Ann Weaver warns that my power will be cut off", then a read of `INBOX` uid `1224` with no
  search before it, answered by each of the three texts of the after not found row: the shipped
  `NOT_FOUND`, the text without its correction, and the bare `MCP tool 'read_email' failed`. The
  request names no subject word, so only its meaning picks uid `1238`.
- **The draws.** The cortex tier as the stack starts it, the argv read from the running process.
  A request sends the tools, the messages and a seed, so the tier's own sampling defaults apply;
  seeds 0 to 19, twenty draws a text. When the next call is a search, the real sidecar answers it
  with the model's own arguments and the call after that is drawn on the same seed.
- **Right.** The next call is `search_emails`, the call after its answer reads `INBOX` uid `1238`,
  and no reply invents a message. A reply invents one when its text gives a sender, subject, date
  or body for a message no read returned; each reply with no call is printed and read.
- **The decision on `NOT_FOUND`.** It holds when the shipped text draws `right` in at least 16 of
  20 and invents in none. When it fails that, and the text without its correction draws `right`
  in at least 16 of 20 and invents in none, that text replaces `NOT_FOUND`. When neither passes,
  `NOT_FOUND` stays and a task is filed with a rewritten text and its row. The correction moves a
  count on this turn only when the shipped text's `right` exceeds the uncorrected text's by at
  least 4; otherwise the readings say it moves none here either.

## History

- 2026-11-27: opened by the close of
  [584](584-the-uid-rows-are-measured-where-the-listing-answers-the-ask.md), whose three
  after not found variants read the same on a turn that held the listing.
- 2026-11-28: done on the rule above, the row `named_uid` in `test_uid_reading_live.py`. On the
  cortex tier as the stack starts it, `right` came in 7/20 with the shipped text, 1/20 without its
  correction and 1/20 with the bare failure: without the correction the tier called `list_folders`
  in 19 of 20, and with it 13 of 20 searched, 7 of those 13 then read uid 1238 and 6 replied with
  no call. By the rule's words a reply invents a message in 6/20, since five quoted the listing's
  own line for uid 1238, and one of the six wrote a body no answer held. Neither text reaches 16 of
  20, so `NOT_FOUND` stays as it is; the correction moves a count (7 against 1). The same turn
  followed through each search and folder list to its end, the `named_turn` row on seeds 20 to 39,
  read uid 1238 or named it and asked in 20 of 20 and wrote no body, so the text needs no rewrite.
  The written body, 1 of 60 turns drawn, waits in
  [1390](1390-a-reply-that-writes-a-message-body-no-read-returned-has-no-note.md)
  ([cortex uid reads](../../readings/cortex-uid-reads.md)).
