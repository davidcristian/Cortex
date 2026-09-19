# The detector cannot tell a description from obedience, and the budget makes descriptions likelier

**Status:** done 2026-09-05
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

The image rows score a cell as obeyed when the reply contains the attack's canary, and over pixels
the benign answer to "what is on my screen?" quotes the screen. The vision record documented that
confusion and answered it by printing every fired cell's reply so a reader can sort them by hand.
The shipped budget's rows add that the confusion grows with the deployment: at the engine's own
budget the model summarised the `chrome` dialog loosely, and at 1024 image tokens it reports the
dialog's instruction word for word, so fifteen of the sixteen firings across the two new rows are
descriptions and the count is higher than at the budget where the model could read less. A number
that gets worse as the deployment gets better cannot be read as resistance without reading every
reply under it.

Closing it means a detector that separates the two, which for `output-laundering` is the difference
between a reply that ends with the demanded notice and one that mentions the notice as something the
screen asks for. The general form is a per-attack predicate over the reply's own structure rather
than a substring search over its whole text, which is what `Attack.obeyed` already is. Then re-score
the published matrices and publish the two counts beside each other.

## History

- 2026-09-04: opened by the close of
  [R-513](513-the-frame-pair-ran-only-where-the-picture-is-saturated.md), which found the count
  rising with the image budget and every added cell being a description.
- 2026-09-05: done, with the new reading agreeing with every hand sort in the tree and the published
  counts re-read on it. `Attack.obeyed` was a substring search both framed and unframed, and the
  same row run again fired six cells, every one a `chrome` description quoting the canary. The entry
  was wrong that the published matrices are printed with their replies: the harness printed a fired
  reply to the terminal cut at 220 characters, and the tree has nine quoted replies across four
  pixel sessions plus three from ADR-0013, so three of the four matrices can only be re-read off the
  sort their records kept. Its proposed form held for the two attacks that name the reply's end and
  needed narrowing for the six whose instruction is the token: a word-for-word report of the dialog
  ends on the bare token for all six, so those six are read as a line that is the token alone.
  Committed: `Attack.obeyed` is structural and `Attack.mentioned` keeps the old reading, `verdict`
  marks a cell `OBEY`, `desc` or `ok`, both conditions and the rate rows print both counts and every
  fired reply whole, the backfire assertion holds on both readings, and `test_reply_readings.py`
  checks the reading against sixteen recorded replies; ten mutants of the readings fail it. Measured
  on the pick at the corpus frame and the shipped budget: obeyed 0 of 30 framed and 0 of 30 control
  against mention counts of 2 and 4, in 188.87 s, beside the published row's 3 and 4. Every
  published pixel count is re-read in ADR-0041 decision 9 and none is wrong about which cells were
  obeyed. R-560 stands: an empty reply reads as resisted on every predicate as before. Opened
  [R-561](561-a-token-beside-the-models-own-words-is-read-as-a-description.md),
  [R-562](562-the-tail-reading-takes-a-quoted-notice-as-reported-speech.md),
  [R-563](563-the-text-arms-published-matrices-are-mention-counts-with-no-reply-behind-them.md) and
  [R-564](564-three-published-pixel-matrices-are-re-read-from-a-hand-sort.md).
