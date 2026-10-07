# Readings: the ports the Windows host refuses

Which TCP ports a process on the development machine cannot bind, and what Docker Desktop does
with a published port it cannot bind. Cited by [ADR-0023](../adr/ADR-0023-body-gateway-volume.md)
decision 6, which sets both sides' default ports, and by
[the overlay runbook](../runbooks/body-overlay.md).

## The refused ports

**2026-10-07.** A shell in a WSL distribution on the Windows host, in mirrored networking mode,
bound and listened on every TCP port from 1024 to 65535 on `127.0.0.1`, without `SO_REUSEADDR`,
and closed each one at once. Nothing from this repository was running. Every refusal was
`EADDRINUSE` (`Address already in use`).

- **1024 to 49151:** 34 ports refused, every one a single port or a pair: 1025 and 1143 (the mail
  Bridge), 2179, 3000, 3306, 5040, 5357, 8000 and others. Each is a process listening on the
  Windows host or in WSL; the ones in WSL show in `ss -ltn`.
- **49152 to 65535, Windows' dynamic port range:** 1,278 ports refused. 1,201 of them form five
  contiguous blocks: 49869 to 49968, 50060 to 50259, 50360 to 51059, 56037 to 56137 and 60119 to
  60218, of 100, 200, 700, 101 and 100 ports. The other 77 are single ports and short runs.
- **The blocks stay, the single ports move.** A second scan 14 minutes later found the same five
  blocks, while 21 single ports had come free and 9 others were taken.
- **`0.0.0.0` matches `127.0.0.1`.** Binding every seventh port of the dynamic range, and the first
  and last port of each block and their outer neighbours, on `0.0.0.0` agreed with the loopback
  scan on 2,481 of 2,489 ports. The 8 others were single ports refused in the first scan only.

The five blocks have the shape of Windows' excluded port ranges, which Hyper-V, WSL and Docker
reserve at boot. They were not listed: interop is off in that distribution, so
`netsh interface ipv4 show excludedportrange protocol=tcp` could not run, and reading the blocks as
those reservations rests on their shape, on their position inside the dynamic range and on their
staying put while the listeners moved. That the blocks move between boots is assumed, not measured
here.

## The range WSL gives Linux

**2026-10-07.** `/proc/sys/net/ipv4/ip_local_port_range` read 43255 to 47350, a 4096-port range
that is not Linux's default of 32768 to 60999. On 2026-08-25 the same file read 44620 to 48715.
Whether the Windows host also refuses its own binds inside that range is not measured.

## A publish inside a block

**2026-10-07.** Docker Desktop's daemon (server 29.8.2), reached through its WSL integration, ran
`redis:8-alpine` with `-p 127.0.0.1:<port>:6379` for six ports, and a dial with a 3 s timeout sent
`PING` to each.

| Port | Where it sits | `docker run` | Published binding in `docker inspect` | Dial |
| --- | --- | --- | --- | --- |
| 50151 | inside 50060 to 50259 | exit 0, running | none | timed out |
| 50259 | last port of that block | exit 0, running | none | timed out |
| 50260 | first port after it | exit 0, running | `127.0.0.1:50260` | `+PONG` |
| 50051 | 9 ports below the block | exit 0, running | `127.0.0.1:50051` | `+PONG` |
| 23051 | below the dynamic range | exit 0, running | `127.0.0.1:23051` | `+PONG` |
| 23151 | below the dynamic range | exit 0, running | `127.0.0.1:23151` | `+PONG` |

A publish inside a block printed no error and left a running container with no published port.
The block's last port and the next one split exactly where the Linux scan split them.

## The default ports

**2026-10-07.** 23051 and 23151 bound on both `127.0.0.1` and `0.0.0.0`. 50151 was refused on
both. 50051 bound. Neither 23051 nor 23151 is assigned in IANA's service name and port number
registry, read the same day.

Method: `scan.py <host> <first> <last> noreuse` binds and listens on each port in turn;
`sample_any.py` takes the `0.0.0.0` sample and `dial.py` the dials. Scripts, JSON results and
logs are in `measurements/windows-port-map-2026-10-07/`.
