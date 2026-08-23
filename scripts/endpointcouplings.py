"""The couplings around each side's own endpoint: the address it answers on, and its port.

One of the data files `crosscheck.py` reads as a single registry, split off `seamcouplings.py` when
the two port sorts grew past half that file and pushed it to the 300-line cap. The seam it fell on
is the one both entries were already written to: an endpoint is not a number two trees compute with
but a place one of them listens and the other dials, restated in compose, in an image, in two
runbooks, in four module contracts and in the sitting notes an operator reads before starting.

Nothing in the scan asks which file an entry sits in, so a coupling moves house without the gate
noticing; what a file buys is a reader who can hold one subject at a time.

**One value per needle, and the digits inside a needle are shape.** Two dozen templates here spell
`127.0.0.1`, and the brain's bind host is one of them. The rest are the body's own bind, the two
`CORTEX_*_ADDR` client defaults, the compose publish's host-side interface and a handful of
loopback dials, each of which goes on saying `127.0.0.1` after the bind host moves. So a value a
needle carries as a literal is SHADOWED and not held: the comparison there runs against the
registry's own text rather than against any declaration, it can only fail in the direction where
the far side moved, and it names the wrong constant when it does. A value gets held by getting an
entry, which is what the bind host now has, and its own needle carries only its own value.
"""

from couplings import Constant, Mention, Site

BASE_COMPOSE = "docker/docker-compose.yml"
BODY_COMPOSE = "docker/docker-compose.body.yml"
BRAIN_DOCKERFILE = "brain/Dockerfile"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_SERVER = "body/app/src-tauri/src/body_server.rs"
RPC_CLIENT = "body/crates/rpc/src/client.rs"
RPC_LIVE = "body/crates/rpc/tests/live.rs"
GATEWAY_LIVE = "brain/packages/body_client/tests/test_gateway_live.py"
SCHEDULE_LIVE = "brain/packages/orchestrator/tests/test_schedule_live_seam.py"
TURN_COST_LIVE = "brain/packages/orchestrator/tests/test_turn_cost_live.py"
SEAM_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
OVERLAY_RUNBOOK = "docs/runbooks/body-overlay.md"
SCHEDULING_RUNBOOK = "docs/runbooks/scheduling.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"
WSL_RUNBOOK = "docs/runbooks/local-dev-wsl.md"
BODY_APP_DOC = "docs/modules/body-app.md"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_RPC_DOC = "docs/modules/body-rpc.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"
HOST_INDEX = "docs/host/index.md"
HOST_BRINGUP = "docs/host/tasks/001-bring-up-and-streamed-turn.md"
HOST_VOLUME_CHECK = "docs/host/tasks/002-core-audio-volume-action.md"
HOST_TOAST_CHECK = "docs/host/tasks/003-real-reminder-toast.md"

ENDPOINT_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the brain's seam bind host",
        why=(
            "the interface BrainService binds when nothing overrides it is restated by the "
            "orchestrator contract as the field's own default, by the RPC contract as the pair "
            "the body's dial address is said to match, and by the WSL runbook's env table as "
            "what an operator gets without exporting anything, so moving the default alone "
            "leaves three documents telling a reader the brain answers somewhere it does not "
            "(ADR-0003 seam-config contract)"
        ),
        sites=(Site(SEAM_CONFIG, "DEFAULT_SEAM_HOST"),),
        # Three places, and not the two dozen needles below that spell the same digits. Those
        # carry four other values: the body's own bind, the two `CORTEX_*_ADDR` client defaults,
        # the compose publish's host-side interface and the loopback dials of a healthcheck, two
        # live suites and two one-liners. Every one of them still says `127.0.0.1` the day this
        # default moves, so reaching them from here would manufacture the coupling the derived
        # literal ruling refuses, wearing the same digits.
        #
        # Two things stay out for the reasons already settled. `docker/docker-compose.yml` sets
        # `CORTEX_SEAM_HOST=0.0.0.0`, which is the shipped override rather than a restatement of
        # the default, and `brain/Dockerfile` says the in-process default is "loopback" without
        # spelling it, which is not a spelling of anything. The ADR that decided this contract is
        # out on the rule that keeps every decision record out.
        #
        # Each needle carries this value and no neighbour's: the RPC contract writes the host and
        # the port on one line and the two entries pay it once each, from opposite ends.
        mentions=(
            Mention(ORCHESTRATOR_DOC, "(`{value}`, `CORTEX_SEAM_HOST`"),
            Mention(BODY_RPC_DOC, "defaults `{value}`/"),
            Mention(WSL_RUNBOOK, "| `CORTEX_SEAM_HOST` | `{value}` |"),
        ),
    ),
    Constant(
        label="the brain's seam port",
        why=(
            "the compose stack publishes this port and dials it in its own healthcheck, the "
            "image declares it, the host body's default endpoints name it, two runbooks and "
            "four module contracts quote it to a reader as the address the brain answers on, "
            "the host sitting's prerequisites tell an operator to expect it, and three live "
            "suites fall back to it when no endpoint is exported, so a change to the server "
            "default alone leaves every one of them pointed at a port nothing listens on "
            "(ADR-0003/0016)"
        ),
        sites=(
            Site(
                "brain/packages/orchestrator/src/cortex_orchestrator/config.py", "DEFAULT_SEAM_PORT"
            ),
        ),
        # The publish is `host:container` and it is the container half that this value names, so
        # its template spells both: `127.0.0.1:{value}` alone was satisfied by the host half and
        # left the half that has to match the server's own default free to drift.
        #
        # The rest is the body port's sort with the trees swapped, on the same tense test: a
        # sentence that becomes WRONG when the port moves is a far side, and one that becomes
        # HISTORY is not. The shapes carry it, so no needle pins the phrasing of a sentence: the
        # stated `CORTEX_BRAIN_ADDR` default, the export a reader copies, the endpoint a snippet
        # dials, an env table's own cell, and a declaring or falling-back file's own prose. Two
        # kinds are deliberately out. The WSL runbook's `port=50051` is one line of captured
        # server output inside a fence, shown to explain how a log renders its fields, which is a
        # dated reading and true still after the default moves. And `test_config.py` asserts this
        # very default three times, which needs no gate: it runs on every commit, so a retune
        # that left it behind fails loudly in the suite that owns it. That is the line between
        # the suites below and that one, and it is the same line `capture_bytes.rs` sits on: a
        # suite that runs on every commit holds itself, and one that does not (`#[ignore]`d
        # there, `integration`-marked here) drifts in silence until somebody measures.
        mentions=(
            Mention(BASE_COMPOSE, '"127.0.0.1:{value}:{value}"'),
            Mention(BASE_COMPOSE, "insecure_channel('127.0.0.1:{value}')"),
            Mention(BRAIN_DOCKERFILE, "EXPOSE {value}"),
            Mention(BODY_COMPOSE, "({value} is the brain's BrainService)"),
            Mention("body/app/src-tauri/src/seam.rs", '"http://127.0.0.1:{value}"'),
            Mention("body/app/src-tauri/src/converse.rs", '"http://127.0.0.1:{value}"'),
            Mention(BODY_SERVER, "`BrainService` being {value}"),
            Mention(RPC_CLIENT, "`http://127.0.0.1:{value}`"),
            Mention(RPC_LIVE, "http://127.0.0.1:{value}", occurrences=2),
            Mention(SCHEDULE_LIVE, 'os.environ.get("CORTEX_SEAM_ENDPOINT", "127.0.0.1:{value}")'),
            Mention(TURN_COST_LIVE, 'os.environ.get("CORTEX_SEAM_ENDPOINT", "127.0.0.1:{value}")'),
            Mention(HOST_INDEX, "`CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:{value}`)"),
            Mention(BODY_APP_DOC, "`CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:{value}`)"),
            Mention(BODY_RPC_DOC, "`http://127.0.0.1:{value}`", occurrences=2),
            Mention(BODY_RPC_DOC, "defaults `127.0.0.1`/`{value}`"),
            Mention(ORCHESTRATOR_DOC, "DEFAULT_SEAM_PORT` ({value},"),
            Mention(ORCHESTRATOR_DOC, "`CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:{value}`)"),
            Mention(OVERLAY_RUNBOOK, "`CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:{value}`)"),
            Mention(OVERLAY_RUNBOOK, 'CORTEX_BRAIN_ADDR = "http://127.0.0.1:{value}"'),
            Mention(WSL_RUNBOOK, "| `CORTEX_SEAM_PORT` | `{value}` |"),
            Mention(WSL_RUNBOOK, "| `CORTEX_BRAIN_ADDR` | `http://127.0.0.1:{value}` |"),
            Mention(WSL_RUNBOOK, 'insecure_channel("127.0.0.1:{value}")'),
            Mention(WSL_RUNBOOK, "insecure_channel('127.0.0.1:{value}')"),
        ),
    ),
    Constant(
        label="the body's own listen port",
        why=(
            "the entry above with the trees swapped: the host body binds this port when nothing "
            "names another, the body override dials it from inside the container, three runbooks "
            "and three module contracts quote it to an operator as the bind and the endpoint, "
            "the host sitting's prerequisites tell an operator to export it, and the brain's "
            "live gateway test falls back to it, so a change to the bind default alone leaves "
            "the container dialling a port the host is not listening on (ADR-0023)"
        ),
        # The one Rust declaration in the ungated Tauri shell. The scan reads it as text, so it
        # is held on every `just check` while the compiler that builds it runs only in CI's
        # `check-shell`, which is the split the entry above already lives with the other way up:
        # the brain declares that port and this same crate spends it twice.
        sites=(Site(BODY_SERVER, "DEFAULT_BODY_PORT"),),
        # Sorted by the survey's tense test: a sentence that becomes WRONG when the port moves is
        # a far side, and one that becomes HISTORY is not. Four shapes carry the sort, so no
        # needle here pins the phrasing of the sentence around the number: `default 127.0.0.1:`
        # for a stated bind, `CORTEX_BODY_ADDR=0.0.0.0:` for the export a container path needs,
        # `host.docker.internal:` for the endpoint the brain dials, and the declaring module's
        # own two doc comments. The volume runbook's record of a fake server once served on
        # `0.0.0.0:50151` is out by that shape alone: it writes the address and not the export,
        # and it is a dated reading rather than an instruction. The three wiring tests are out
        # too, each setting `CORTEX_BODY_ENDPOINT` to a string and asserting the composition root
        # read it back, which any port would pass; tying a fixture to a deployment default would
        # redden on a change that broke nothing. The four `docs/host/` files are IN, and that is
        # the judgement this entry settles: a host file is a live instruction, not a record.
        # Its prerequisites open "Sittings die on setup. Have these before starting", and a
        # completed check's file shrinks to a heading, its status and a pointer, so the sentence
        # naming this port exists only while somebody may still read it and act on it.
        mentions=(
            Mention(BODY_SERVER, "default `127.0.0.1:{value}`"),
            Mention(BODY_SERVER, "CORTEX_BODY_ADDR=0.0.0.0:{value}"),
            Mention(BODY_COMPOSE, "${CORTEX_BODY_ENDPOINT:-host.docker.internal:{value}}"),
            Mention(BODY_COMPOSE, "default 127.0.0.1:{value}"),
            Mention(BODY_COMPOSE, "(0.0.0.0:{value})"),
            Mention(BODY_COMPOSE, "{value} is the"),
            Mention(BODY_GATEWAY, "``host:{value}``"),
            Mention(GATEWAY_LIVE, 'os.environ.get("CORTEX_BODY_ENDPOINT", "127.0.0.1:{value}")'),
            Mention(GATEWAY_LIVE, "host.docker.internal:{value}"),
            Mention(VOLUME_RUNBOOK, "`CORTEX_BODY_ADDR` (default `127.0.0.1:{value}`)"),
            Mention(VOLUME_RUNBOOK, "host.docker.internal:{value}", occurrences=2),
            Mention(VOLUME_RUNBOOK, "CORTEX_BODY_ADDR=0.0.0.0:{value}", occurrences=2),
            Mention(WSL_RUNBOOK, "| `CORTEX_BODY_ADDR` | `127.0.0.1:{value}` |"),
            Mention(WSL_RUNBOOK, "host.docker.internal:{value}"),
            Mention(WSL_RUNBOOK, "0.0.0.0:{value}"),
            Mention(SCHEDULING_RUNBOOK, "`CORTEX_BODY_ADDR=0.0.0.0:{value}`"),
            Mention(HOST_INDEX, "CORTEX_BODY_ADDR=0.0.0.0:{value}"),
            Mention(HOST_BRINGUP, '"0.0.0.0:{value}"'),
            Mention(HOST_VOLUME_CHECK, "CORTEX_BODY_ADDR=0.0.0.0:{value}"),
            Mention(HOST_TOAST_CHECK, "CORTEX_BODY_ADDR=0.0.0.0:{value}"),
            Mention(BODY_APP_DOC, "default `127.0.0.1:{value}`", occurrences=2),
            Mention(BODY_CLIENT_DOC, "host.docker.internal:{value}"),
            Mention(ORCHESTRATOR_DOC, "host.docker.internal:{value}"),
        ),
    ),
)
