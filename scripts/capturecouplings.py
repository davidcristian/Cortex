"""The couplings around one capture: the size asked for, the reply allowed, and the deadlines."""

from couplings import Constant, Mention, Site

BODY_COMPOSE = "docker/docker-compose.body.yml"
GPU_COMPOSE = "docker/docker-compose.gpu.yml"
IMAGES = "brain/packages/core/src/cortex_core/images.py"
BODY_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_body.py"
INFERENCE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_CONFIG_TEST = "brain/packages/orchestrator/tests/test_config.py"
SCREEN_POLICY = "body/crates/core/src/os/screen_policy.rs"
SEAM_PROTO = "proto/body.proto"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_CORE_DOC = "docs/modules/body-core-capture.md"
CAPTURE_BYTES = "body/crates/core/tests/capture_bytes.rs"
CAPTURE_CHECK = "docs/host/tasks/012-display-capture-path.md"
MODEL_MANAGER_DOC = "docs/modules/brain-model-manager.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator-config.md"
GPU_RUNBOOK = "docs/runbooks/llamacpp-gpu.md"
VISION_RUNBOOK = "docs/runbooks/vision.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"

CAPTURE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the capture call's shipped deadline",
        why=(
            "the compose stack writes this default into every container it starts and two "
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
            "the same four places write the short deadline the volume and notify calls run "
            "under, so the setting an operator reads and the number the adapter uses are one value "
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
    Constant(
        label="the capture edge's shipped default",
        why=(
            "the compose stack ships this edge into every container, two runbooks and three "
            "module contracts quote it as the brain half of the measured legibility pair, and "
            "the body's own headroom suite sizes its worst case on it, so retuning the field "
            "alone would leave every deployment asking for the old edge while the encoder was "
            "sized for the new one (ADR-0029 decision 17)"
        ),
        sites=(Site(BODY_CONFIG, "DEFAULT_CAPTURE_MAX_EDGE"), Site(CAPTURE_BYTES, "BRAIN_EDGE")),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CAPTURE_MAX_EDGE:-{value}}"),
            Mention(BODY_COMPOSE, "defaults to {value} rather"),
            Mention(BODY_CONFIG, "asks for {value} rather"),
            Mention(CAPTURE_BYTES, "a {value} px capture by default"),
            Mention(CAPTURE_BYTES, "a {value} px capture costs"),
            Mention(CAPTURE_BYTES, "resampled to {value} px"),
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
        label="the body's own default edge",
        why=(
            "a caller that names no size gets this edge, and every place that states the brain's "
            "own default states it as a departure from this one, in both trees and in the proto, "
            "so retuning the body alone would leave all of them explaining a choice against a "
            "number nothing answers with any more (ADR-0029)"
        ),
        sites=(Site(SCREEN_POLICY, "DEFAULT_MAX_EDGE"),),
        mentions=(
            Mention(SCREEN_POLICY, "{value} is chosen from measurement"),
            Mention(SCREEN_POLICY, "{value} keeps a little"),
            Mention(CAPTURE_BYTES, "than the {value} px view"),
            Mention(CAPTURE_BYTES, "than a {value} px one"),
            Mention(IMAGES, "the body's {value} px default edge"),
            Mention(BODY_CONFIG, "the body's own {value},"),
            Mention(BODY_CONFIG, "its own conservative {value}"),
            Mention(BODY_CONFIG_TEST, "body's own default is {value}"),
            Mention(BODY_COMPOSE, "the body's own {value}, which"),
            Mention(SEAM_PROTO, 'default" ({value})'),
            Mention(BODY_CORE_DOC, "`DEFAULT_MAX_EDGE` ({value})"),
            Mention(ORCHESTRATOR_DOC, "own {value} because the pixels"),
            Mention(VISION_RUNBOOK, "body's own default ({value})"),
            Mention(GPU_RUNBOOK, "to its own {value} px default"),
            Mention(GPU_RUNBOOK, "a {value} px picture"),
            Mention(GPU_RUNBOOK, "{value} px default)."),
            Mention(GPU_RUNBOOK, "below even the {value} px view"),
        ),
    ),
    Constant(
        label="the capture byte budget's shipped default",
        why=(
            "the brain's budget defaults to the body's own ceiling, and the stack writes that "
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
