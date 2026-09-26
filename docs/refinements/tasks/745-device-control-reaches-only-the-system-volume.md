# Device control reaches only the system volume

**Status:** open, waiting for its trigger
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** The maintainer picks a route below, or names the native actions a first slice builds.
**Verified:** 2026-09-26

The assistant changes one thing on its machine, the system volume, through the cortex-only built-ins
`get_volume` and `set_volume` over `BodyGateway`. `notify` and `capture_screen` use the same port but
change nothing, and `InjectInput` waits for a consumer ([222](222-injectinput-rpc.md)). Nothing
reaches a device off this machine. Home Assistant and HASS.Agent appear nowhere in the repo or its
history, so the plan to use them was never written down until now.

## Proposal

Two routes that work together: native actions for this machine, Home Assistant for every other device.

**Route one, more native actions.** Each is a `BodyService` RPC, a `cfg` OS trait with a Windows
adapter, and a built-in tool, the way volume was built. Each Windows adapter is validated as a host
task. Native actions work with no network and no Home Assistant. The confirmation column follows
ADR-0023 decision 4: a reversible change to host state needs none. The Windows calls are
assumptions until each is built.

| Action | Windows call | Confirmation |
| --- | --- | --- |
| Media play, pause, next, previous | system media transport controls | none |
| Brightness, built-in panel only | WMI `WmiMonitorBrightnessMethods` | none |
| Lock the session | `LockWorkStation` | none |
| Sleep | `SetSuspendState` | required |
| Open an app or a URL | `ShellExecuteW` | required, outbound |
| Shut down or restart | `InitiateShutdownW` | required |

**Route two, Home Assistant through its MCP server.** Home Assistant's `mcp_server` integration
serves the entities exposed to its Assist API at `/api/mcp` over streamable HTTP, authorized by a
long-lived access token. The brain is already a streamable HTTP MCP client, with an endpoint and an
allowlist per server ([ADR-0009](../../adr/ADR-0009-tools-mcp.md) decision 8), so Home Assistant is
one more endpoint and needs no sidecar. The code has three gaps:

1. `streamable_http_session(url)` sends no headers, so it cannot send the token. The fix is a
   per-endpoint secret, read from the environment and kept out of every log line.
2. Subagents receive every MCP tool that needs no confirmation (`ConfirmFreeToolRegistry`,
   [ADR-0010](../../adr/ADR-0010-subagents.md) decision 4). The subagent pick obeys 9 of 100 framed
   injection draws against the cortex's 0 ([ADR-0017](../../adr/ADR-0017-subagent-model-safety.md)).
   A device tool stays cortex-only, as volume is, so an endpoint needs a setting that keeps its tools
   from subagents.
3. Confirmation is keyed by tool name, and Home Assistant's tools are generic: one turn-on tool acts
   on every exposed entity, so a name cannot tell a lamp from a door lock. The recommended boundary is
   Home Assistant's own exposure list, as the read-only mount is the filesystem server's boundary.
   Expose lights, media players and climate, which are reversible and need no confirmation. Never
   expose locks, garage doors or alarm panels. Confirming per entity would be a new dispatch rule,
   built only when a lock should be reachable.

Whether the brain container reaches a Home Assistant server on the LAN is unmeasured on this
machine. The live test needs no hardware: the Home Assistant container image with its `demo`
integration exposes simulated lights and media players.

**HASS.Agent's place.** HASS.Agent is a Windows app that publishes a PC's sensors and commands to
Home Assistant over MQTT. Cortex does not use it for this machine, because the body acts directly,
with no broker or Home Assistant in the path. It is useful beside Cortex. It lets Home Assistant
automations use this PC, and through route two it lets the assistant control other PCs that run
it. Cortex writes no code for it. When both run, keep this PC's HASS.Agent entities off the Assist
exposure list, or the model has two tools for one volume.

**What closes it.** Each route closes as its own slice with an ADR. Route two can start at any time
against the container, and needs the maintainer's instance only for its live row. Route one needs
the maintainer to pick an action group, which is then built. Declined if neither route is wanted.

## History

- 2026-09-26: filed on the maintainer's request, as a proposal with no implementation.
