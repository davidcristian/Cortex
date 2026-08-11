# The structured confirm-resolution event

**Status:** landed 2026-07-14
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

The structured confirm-resolution event is recorded at the [ADR-0022 resolution
addendum](../../adr/ADR-0022-email-write-confirmer.md). This entry's cost estimate was the
understated kind the section warns about: it read as an overlay refinement, and it is a
**seam change**, because `ServerEvent` had no way to say a confirmation ended (`ConfirmRequest`
was the only confirm event the brain could emit, and `SeamConfirmer.confirm` just returned
`False` on timeout). So it touched the proto, both committed stub trees, the confirmer, the
Rust port + adapter, the Tauri shell's serde mirror, and the reducer. `ConfirmResolved
{confirm_id, outcome}` (field 7) is emitted **only for the endings the client cannot already
know**: the confirm timeout (`"timeout"`) and client input half-closing (`"unavailable"`).
Not the user's own answer (the client authored it and closed its own card), not a cancelled
or torn-down turn (its terminal event closes the card, as it always has), and not an ask
refused after `close`, which emitted no request and so has no card to close. That table is
the contract: the overlay's rule is one line ("a resolution for the card I am showing closes
it"), and everything absent from it was already handled. `outcome` is a string, like
`SeamError.code` and `StatusUpdate.state`, so no version skew needs an unknown-enum branch;
the overlay renders none of it, because the model's own reply is the explanation surface
(`USER_DECLINED_MSG` tells it to relay the declined action) and a card lingering to repeat
that would be a second account of one fact. The field rides the wire documented anyway, the
`DueReminder.session_id` precedent. Two behaviours fall out of the card being gone rather
than needing code: the second-121 Approve click cannot reach the bridge (`respondConfirm`
already refuses anything that is not the live question), and the explicit deny every
turn-ending path sends is skipped for a confirm the brain resolved, keeping the answer the
user never gave off the wire. The reducer action for the user answering was renamed
`confirmAnswered` to free the name.
