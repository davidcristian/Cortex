"""The couplings across the language boundary: one value two trees' code must both hold."""

from couplings import Constant, Mention, Relation, Site

BASE_COMPOSE = "docker/docker-compose.yml"
BODY_COMPOSE = "docker/docker-compose.body.yml"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_SERVER = "body/app/src-tauri/src/body_server.rs"
GATEWAY_LIVE = "brain/packages/body_client/tests/test_gateway_live.py"
SCHEDULING_RUNBOOK = "docs/runbooks/scheduling.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"
WSL_RUNBOOK = "docs/runbooks/local-dev-wsl.md"
BODY_APP_DOC = "docs/modules/body-app.md"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"
HOST_INDEX = "docs/host/index.md"
HOST_BRINGUP = "docs/host/tasks/001-bring-up-and-streamed-turn.md"
HOST_VOLUME_CHECK = "docs/host/tasks/002-core-audio-volume-action.md"
HOST_TOAST_CHECK = "docs/host/tasks/003-real-reminder-toast.md"

SEAM_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the screen-capture byte ceiling",
        why=(
            "the brain sends its own budget as the capture request's max_bytes and re-verifies "
            "it on receipt, so a body ceiling above the brain's would let a capture pass the "
            "body and be refused in the brain (ADR-0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_CAPTURE_BYTES"),
            Site("brain/packages/core/src/cortex_core/images.py", "MAX_IMAGE_BYTES"),
        ),
    ),
    Constant(
        label="the seam token's metadata key",
        why=(
            "each side attaches the token under this key and the other reads it back out, in "
            "both seam directions, so a disagreement fails every authenticated call (ADR-0016)"
        ),
        sites=(
            Site("body/crates/rpc/src/auth.rs", "SEAM_TOKEN_HEADER"),
            Site("body/crates/rpc/src/call.rs", "SEAM_TOKEN_HEADER"),
            Site("brain/packages/seam/src/cortex_seam/__init__.py", "SEAM_TOKEN_HEADER"),
        ),
        # The fourth copy, and the one whose drift would be silent: the brain container's own
        # healthcheck dials Health with the token attached, from a Python one-liner inside YAML.
        mentions=(Mention(BASE_COMPOSE, "'{value}'"),),
    ),
    Constant(
        label="the session-title truncation bound",
        why=(
            "the brain bounds every title it lists to this, and the overlay bounds the live "
            "title it derives for a chat the brain has not listed yet, so a disagreement shows "
            "one chat under two names at once: the header cut at one bound while its own "
            "switcher row carries the other (ADR-0021)"
        ),
        sites=(
            Site("brain/packages/core/src/cortex_core/sessions.py", "TITLE_MAX"),
            Site("body/app/src/overlay/sessionState.ts", "TITLE_MAX"),
        ),
    ),
    Constant(
        label="the capture edge ceiling under the brain's image bound",
        why=(
            "the body clamps every request to its own ceiling and the brain refuses any image "
            "past its bound, so a body ceiling above the brain's would spend a real capture on "
            "an image the brain then throws away (ADR-0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_EDGE_CEILING"),
            Site("brain/packages/core/src/cortex_core/images.py", "MAX_IMAGE_EDGE"),
        ),
        relation=Relation.ORDERED,
    ),
    Constant(
        label="the capture encoding inside the brain's allow-list",
        why=(
            "the body encodes every capture as this one type and the brain refuses any image "
            "whose type its allow-list does not carry, so an encoding the list lost would spend "
            "a real capture on an image the brain then throws away (ADR-0029)"
        ),
        # The value first and the collection last, which is the order this relation reads: the
        # body produces one encoding, the brain accepts a set of them, and the tie is that the
        # one is among the several. Neither an equality (the sets differ) nor an ordering.
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "CAPTURE_MIME"),
            Site("brain/packages/core/src/cortex_core/images.py", "ALLOWED_MIME_TYPES"),
        ),
        relation=Relation.MEMBER,
    ),
    Constant(
        label="the body-client receive limit above the capture ceiling",
        why=(
            "a capture rides back to the brain as one gRPC message, so a receive limit at or "
            "below the byte ceiling would refuse in the transport a capture both policies "
            "allowed, and the refusal would read as a body fault (ADR-0023/0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_CAPTURE_BYTES"),
            Site(BODY_GATEWAY, "MAX_RECEIVE_BYTES"),
        ),
        relation=Relation.ORDERED,
    ),
    Constant(
        label="the capture-screen tool's name",
        why=(
            "the brain names the tool and the overlay lights its capture dot by matching that "
            "name off the wire, so a rename leaves the dot dark on every capture (ADR-0029)"
        ),
        sites=(
            Site("brain/packages/core/src/cortex_core/screen_tool.py", "CAPTURE_SCREEN_TOOL_NAME"),
            Site("body/app/src/overlay/turnState.ts", "CAPTURE_SCREEN_TOOL"),
        ),
    ),
    Constant(
        label="the reasoning trace's status state",
        why=(
            "the brain sends deliberation under this state and the overlay accumulates the "
            "trace and styles its chip by comparing against the bare literal, so a rename "
            "leaves the reasoning unaccumulated and the chip unstyled (ADR-0020)"
        ),
        sites=(Site("brain/packages/core/src/cortex_core/output_channels.py", "THINKING_STATE"),),
        # The component's two comparisons are one set: the same chip's class and its accessible
        # name, both deciding on this one state. A rename applied to one of them leaves the other
        # dead with the file still spelling the new value, which is what the count refuses.
        mentions=(
            Mention("body/app/src/overlay/turnState.ts", 'event.state === "{value}"'),
            Mention(
                "body/app/src/components/Message.tsx",
                'message.statusState === "{value}"',
                occurrences=2,
            ),
        ),
    ),
    Constant(
        label="the brain's seam port",
        why=(
            "the compose stack publishes this port and dials it in its own healthcheck, and the "
            "host body's default endpoints name it too, so a change to the server default alone "
            "leaves every one of them pointed at a port nothing listens on (ADR-0003/0016)"
        ),
        sites=(
            Site(
                "brain/packages/orchestrator/src/cortex_orchestrator/config.py", "DEFAULT_SEAM_PORT"
            ),
        ),
        # The publish is `host:container` and it is the container half that this value names, so
        # its template spells both: `127.0.0.1:{value}` alone was satisfied by the host half and
        # left the half that has to match the server's own default free to drift.
        mentions=(
            Mention(BASE_COMPOSE, '"127.0.0.1:{value}:{value}"'),
            Mention(BASE_COMPOSE, "insecure_channel('127.0.0.1:{value}')"),
            Mention("body/app/src-tauri/src/seam.rs", '"http://127.0.0.1:{value}"'),
            Mention("body/app/src-tauri/src/converse.rs", '"http://127.0.0.1:{value}"'),
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
        sites=(Site(BODY_SERVER, "DEFAULT_BODY_PORT"),),
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
