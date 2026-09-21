"""The couplings around each side's endpoint: the address it listens on, and its port."""

from couplings import Constant, Mention, Site

BASE_COMPOSE = "docker/docker-compose.yml"
BODY_COMPOSE = "docker/docker-compose.body.yml"
BRAIN_DOCKERFILE = "brain/Dockerfile"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_SERVER = "body/app/src-tauri/src/body_server.rs"
RPC_CLIENT = "body/crates/rpc/src/client.rs"
RPC_LIVE = "body/crates/rpc/tests/live.rs"
GATEWAY_LIVE = "brain/packages/body_client/tests/test_gateway_live.py"
SCHEDULE_LIVE = "brain/packages/orchestrator/tests/test_schedule_grpc_live.py"
TURN_COST_LIVE = "brain/packages/orchestrator/tests/test_turn_cost_live.py"
SEAM_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
OVERLAY_RUNBOOK = "docs/runbooks/body-overlay.md"
SCHEDULING_RUNBOOK = "docs/runbooks/scheduling.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"
WSL_RUNBOOK = "docs/runbooks/local-dev-wsl.md"
BODY_APP_DOC = "docs/modules/body-app.md"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_RPC_DOC = "docs/modules/body-rpc.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator-config.md"
HOST_INDEX = "docs/host/index.md"
HOST_BRINGUP = "docs/host/tasks/001-bring-up-and-streamed-turn.md"
HOST_VOLUME_CHECK = "docs/host/tasks/002-core-audio-volume-action.md"
HOST_TOAST_CHECK = "docs/host/tasks/003-real-reminder-toast.md"

ENDPOINT_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the brain's gRPC bind host",
        why=(
            "the interface BrainService binds when nothing overrides it is restated by the "
            "orchestrator contract as the field's own default, by the RPC contract as the pair "
            "the body's dial address is said to match, and by the WSL runbook's env table as "
            "what an operator gets without exporting anything, so moving the default alone "
            "leaves three documents telling a reader the brain answers somewhere it does not "
            "(the endpoint configuration contract in ADR-0003)"
        ),
        sites=(Site(SEAM_CONFIG, "DEFAULT_SEAM_HOST"),),
        mentions=(
            Mention(ORCHESTRATOR_DOC, "(`{value}`, `CORTEX_SEAM_HOST`"),
            Mention(BODY_RPC_DOC, "defaults `{value}`/"),
            Mention(WSL_RUNBOOK, "| `CORTEX_SEAM_HOST` | `{value}` |"),
        ),
    ),
    Constant(
        label="the brain's gRPC port",
        why=(
            "the compose stack publishes this port and dials it in its own healthcheck, the image "
            "declares it, the host body's default endpoints name it, two runbooks and four module "
            "contracts quote it to a reader as the address the brain answers on, the host "
            "measurement session's prerequisites tell an operator to expect it, and three live "
            "suites fall back to it when no endpoint is exported, so a change to the server "
            "default alone leaves every one of them pointed at a port nothing listens on "
            "(ADR-0003/0016)"
        ),
        sites=(
            Site(
                "brain/packages/orchestrator/src/cortex_orchestrator/config.py", "DEFAULT_SEAM_PORT"
            ),
        ),
        mentions=(
            Mention(BASE_COMPOSE, '"127.0.0.1:{value}:{value}"'),
            Mention(BASE_COMPOSE, "insecure_channel('127.0.0.1:{value}')"),
            Mention(BRAIN_DOCKERFILE, "EXPOSE {value}"),
            Mention(BODY_COMPOSE, "({value} is the brain's BrainService)"),
            Mention("body/app/src-tauri/src/brain.rs", '"http://127.0.0.1:{value}"'),
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
            "and three module contracts quote it to an operator as the bind and the endpoint, the "
            "host measurement session's prerequisites tell an operator to export it, and the "
            "brain's live gateway test falls back to it, so a change to the bind default alone "
            "leaves the container dialling a port the host is not listening on (ADR-0023)"
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
