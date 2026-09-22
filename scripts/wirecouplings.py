"""The couplings across the language boundary: one value both trees' code must have."""

from couplings import Constant, Mention, Relation, Site

BASE_COMPOSE = "docker/docker-compose.yml"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"

WIRE_COUPLINGS: tuple[Constant, ...] = (
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
        label="the gRPC token's metadata key",
        why=(
            "each side attaches the token under this key and the other reads it back out, in both "
            "directions across the boundary, so a disagreement fails every authenticated call "
            "(ADR-0016)"
        ),
        sites=(
            Site("body/crates/rpc/src/auth.rs", "SEAM_TOKEN_HEADER"),
            Site("body/crates/rpc/src/call.rs", "SEAM_TOKEN_HEADER"),
            Site("brain/packages/seam/src/cortex_seam/__init__.py", "SEAM_TOKEN_HEADER"),
        ),
        mentions=(Mention(BASE_COMPOSE, "'{value}'"),),
    ),
    Constant(
        label="the session-title truncation bound",
        why=(
            "the brain bounds every title it lists to this, and the overlay bounds the live "
            "title it derives for a chat the brain has not listed yet, so a disagreement shows "
            "one chat under two names at once: the header cut at one bound while its own "
            "switcher row has the other (ADR-0021)"
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
            "whose type its allow-list does not contain, so an encoding the list lost would spend "
            "a real capture on an image the brain then throws away (ADR-0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "CAPTURE_MIME"),
            Site("brain/packages/core/src/cortex_core/images.py", "ALLOWED_MIME_TYPES"),
        ),
        relation=Relation.MEMBER,
    ),
    Constant(
        label="the body-client receive limit above the capture ceiling",
        why=(
            "a capture goes back to the brain as one gRPC message, so a receive limit at or "
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
        label="the heartbeat period",
        why=(
            "the brain sends a heartbeat once per period while a turn runs, and the body counts "
            "each one it receives as a period of the turn's silence, so a disagreement ends a "
            "delegated turn early or lets a stalled one run past its bound (ADR-0069)"
        ),
        sites=(
            Site("body/crates/core/src/retry/gap.rs", "HEARTBEAT_PERIOD_MS"),
            Site(
                "brain/packages/orchestrator/src/cortex_orchestrator/converse_stream.py",
                "HEARTBEAT_PERIOD_MS",
            ),
        ),
    ),
    Constant(
        label="the reasoning trace's status state",
        why=(
            "the brain sends deliberation under this state and the overlay accumulates the "
            "trace and styles its chip by comparing against the bare literal, so a rename "
            "leaves the reasoning unaccumulated and the chip unstyled (ADR-0020)"
        ),
        sites=(Site("brain/packages/core/src/cortex_core/waits.py", "THINKING"),),
        mentions=(
            Mention("body/app/src/overlay/turnState.ts", 'event.state === "{value}"'),
            Mention("body/app/src/overlay/turnState.ts", 'event.wait === "{value}"'),
            Mention(
                "body/app/src/components/Message.tsx",
                'message.statusState === "{value}"',
                occurrences=2,
            ),
        ),
    ),
)
