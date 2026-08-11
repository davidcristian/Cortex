# A safe Core Audio wrapper

**Status:** open, fix when it bites
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** A fully-safe wrapper crate over the COM audio API maturing.

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

`WindowsAudioControl` uses the ADR-0023-scoped `unsafe` over the
`windows` crate's COM API; a fully-safe wrapper crate (à la `global-hotkey` for the hotkey) would
retire the exception if one matures.
