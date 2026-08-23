"""The couplings around one capture: what the brain asks for, holds the reply to, and waits."""

from couplings import Constant, Mention, Site

BODY_COMPOSE = "docker/docker-compose.body.yml"
GPU_COMPOSE = "docker/docker-compose.gpu.yml"
IMAGES = "brain/packages/core/src/cortex_core/images.py"
BODY_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_body.py"
INFERENCE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_CORE_DOC = "docs/modules/body-core.md"
CAPTURE_BYTES = "body/crates/core/tests/capture_bytes.rs"
CAPTURE_CHECK = "docs/host/tasks/012-display-capture-path.md"
MODEL_MANAGER_DOC = "docs/modules/brain-model-manager.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"
GPU_RUNBOOK = "docs/runbooks/llamacpp-gpu.md"
VISION_RUNBOOK = "docs/runbooks/vision.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"

CAPTURE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the capture call's shipped deadline",
        why=(
            "the compose stack spells this default into every container it starts and two "
            "runbooks quote it as the number an operator is running, so retuning the adapter "
            "alone would leave every deployment waiting the old one (ADR-0029)"
        ),
        sites=(Site(BODY_GATEWAY, "DEFAULT_CAPTURE_TIMEOUT_S"),),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CAPTURE_TIMEOUT_S:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CAPTURE_TIMEOUT_S` | brain | `{value}` |"),
            Mention(VOLUME_RUNBOOK, "`CORTEX_BODY_CAPTURE_TIMEOUT_S` (default `{value}`)"),
            Mention(BODY_CLIENT_DOC, "`DEFAULT_CAPTURE_TIMEOUT_S = {value}`"),
        ),
    ),
    Constant(
        label="the other calls' shipped deadline",
        why=(
            "the same four places spell the short deadline the volume and notify calls run "
            "under, so the knob an operator reads and the number the adapter uses are one value "
            "or they are a documented lie (ADR-0029)"
        ),
        sites=(Site(BODY_GATEWAY, "DEFAULT_CALL_TIMEOUT_S"),),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CALL_TIMEOUT_S:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CALL_TIMEOUT_S` | brain | `{value}` |"),
            Mention(VOLUME_RUNBOOK, "`CORTEX_BODY_CALL_TIMEOUT_S` (default `{value}`)"),
            Mention(BODY_CLIENT_DOC, "`DEFAULT_CALL_TIMEOUT_S = {value}`"),
        ),
    ),
    # The two capture bounds that ride with a request. The byte budget is the brain's half of a
    # ceiling the body enforces too, so it is a site in `seamcouplings.py` as well; here it is the
    # shipped number three deployment surfaces restate. The edge is the brain's alone.
    Constant(
        label="the capture edge's shipped default",
        why=(
            "the compose stack ships this edge into every container, two runbooks and three "
            "module contracts quote it as the brain half of the measured legibility pair, and "
            "the body's own headroom suite sizes its worst case on it, so retuning the field "
            "alone would leave every deployment asking for the old edge while the encoder was "
            "sized for the new one (ADR-0029 legibility addendum)"
        ),
        # The second site is the other tree's: `capture_bytes.rs` names the edge the brain asks
        # for and measures how much room the byte ceiling leaves at it, so a retune here alone
        # leaves that suite reporting headroom for a capture nothing requests any more.
        sites=(Site(BODY_CONFIG, "DEFAULT_CAPTURE_MAX_EDGE"), Site(CAPTURE_BYTES, "BRAIN_EDGE")),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CAPTURE_MAX_EDGE:-{value}}"),
            Mention(BODY_COMPOSE, "defaults to {value} rather"),
            Mention(BODY_CONFIG, "defaults to **{value} rather"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CAPTURE_MAX_EDGE` | brain | `{value}` |"),
            Mention(VISION_RUNBOOK, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(VISION_RUNBOOK, "{value} px capture"),
            Mention(VISION_RUNBOOK, "`{value}` is the brain half"),
            Mention(GPU_RUNBOOK, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}", occurrences=2),
            Mention(GPU_COMPOSE, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(MODEL_MANAGER_DOC, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(ORCHESTRATOR_DOC, "DEFAULT_CAPTURE_MAX_EDGE` ({value})"),
            Mention(BODY_CORE_DOC, "{value} px edge"),
            Mention(CAPTURE_CHECK, "at {value} px"),
        ),
    ),
    Constant(
        label="the capture byte budget's shipped default",
        why=(
            "the brain's budget defaults to the body's own ceiling, and the stack spells that "
            "number again while the vision runbook quotes it as the shipped budget and again as "
            "the top of the range the field accepts, so a tightened ceiling with either left "
            "alone would ask every deployment for more bytes than either end now allows "
            "(ADR-0029)"
        ),
        sites=(Site(IMAGES, "MAX_IMAGE_BYTES"),),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_MAX_IMAGE_BYTES:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_MAX_IMAGE_BYTES` | brain | `{value}` |"),
            Mention(VISION_RUNBOOK, "outside `1..{value}`"),
        ),
    ),
    Constant(
        label="whether capture is advertised, as shipped",
        why=(
            "the body override names the probe policy every deployment boots on and the vision "
            "runbook states it as the shipped answer, so a retuned field with the substitution "
            "left alone would keep probing where the brain had decided not to (ADR-0029)"
        ),
        sites=(Site(INFERENCE_CONFIG, "DEFAULT_VISION_MODE"),),
        mentions=(
            Mention(BODY_COMPOSE, '"${CORTEX_VISION:-{value}}"'),
            Mention(VISION_RUNBOOK, "| `CORTEX_VISION` | brain | `{value}` |"),
        ),
    ),
)
