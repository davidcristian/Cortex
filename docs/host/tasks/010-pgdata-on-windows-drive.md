# PGDATA directly on the Windows drive

**Status:** done 2026-10-07
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

A Postgres data directory bound onto the Windows drive ran under Docker Desktop on 2026-10-07:
initdb passed because the drive's drvfs share stores Linux owners, the server came back after a
restart, and commits ran at the named volume's rate, while a bulk load took 13 times as long
([readings](../../readings/pgdata-windows-drive.md)). The named volume stays the default
([ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 7).

## History

- 2026-07-19: the host index created that list naming a second example beside this one, the
  resident VRAM figure with the projector loaded, and withdrew that example the same day on finding
  it was no host item at all. This check is the half that stood.
- 2026-10-07: done by the agent. The check needs only Docker Desktop on the Windows host, and the
  WSL shell reaches that same daemon through its WSL integration, so a bind onto a folder on the
  Windows drive ran beside a fresh named volume with no Win32 session. A source written as a
  Windows path from PowerShell was not run; the readings name the mount it is assumed to use.
