# The structured confirm-resolution event

**Status:** done 2026-07-14
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Recorded at [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) decision 7. The entry read as an
overlay refinement and is a change to the body-brain interface, because `ServerEvent` had no way to
say a confirmation ended: `ConfirmRequest` was the only confirm event the brain could emit, and
`SeamConfirmer.confirm` just returned `False` on timeout. So it touched the proto, both committed
stub trees, the confirmer, the Rust port and adapter, the Tauri shell's serde mirror, and the
reducer.

`ConfirmResolved {confirm_id, outcome}` (field 7) is emitted only for the endings the client cannot
already know: the confirm timeout (`"timeout"`) and client input half-closing (`"unavailable"`). Not
the user's own answer, since the client authored it and closed its own card; not a cancelled or torn
down turn, whose terminal event closes the card; and not an ask refused after `close`, which emitted
no request. That table is the contract, and the overlay's rule is one line: a resolution for the card
I am showing closes it.

`outcome` is a string, like `SeamError.code` and `StatusUpdate.state`, so no version skew needs an
unknown-value branch. The overlay renders none of it, because the model's own reply is the
explanation (`USER_DECLINED_MSG` tells it to relay the declined action) and a card lingering to
repeat that would be a second account of one fact.

Two behaviours follow from the card being gone rather than needing code: a late Approve click cannot
reach the bridge, since `respondConfirm` already refuses anything that is not the live question, and
the explicit deny every turn-ending path sends is skipped for a confirm the brain resolved, keeping
an answer the user never gave off the wire. The reducer action for the user answering was renamed
`confirmAnswered` to free the name.

## History

- 2026-07-14: Closed, and it cost more than the entry estimated, being an interface change rather
  than an overlay one.
