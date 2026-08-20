"""The couplings around a shipped number: one tree declares it, and other files restate it."""

from couplings import Constant, Mention, Site, Spelling

BASE_COMPOSE = "docker/docker-compose.yml"
BODY_COMPOSE = "docker/docker-compose.body.yml"
GPU_COMPOSE = "docker/docker-compose.gpu.yml"
LOG_FORMAT = "brain/packages/core/src/cortex_core/log_format.py"
SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_CORE_DOC = "docs/modules/body-core.md"
BODY_RPC_DOC = "docs/modules/body-rpc.md"
RETRY_PLAN = "body/crates/core/src/retry/plan.rs"
VISION_RUNBOOK = "docs/runbooks/vision.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"

SHIPPED_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the salience limit's shipped default",
        why=(
            "the compose stack spells the core's default into every container it starts, so "
            "retuning the core constant alone would leave every deployment still running the "
            "old number with nothing saying so (ADR-0009 salience addendum)"
        ),
        sites=(
            Site(
                "brain/packages/core/src/cortex_core/tool_salience.py", "MAX_IDENTICAL_DISPATCHES"
            ),
        ),
        # The knob's compose default, which is a shell substitution rather than a declaration:
        # there is nothing to parse on that side, so the agreed number is rendered into the
        # shape and required to appear.
        mentions=(Mention(BASE_COMPOSE, "${CORTEX_TOOLS_SALIENCE_LIMIT:-{value}}"),),
    ),
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
    Constant(
        label="the grace between the announced deadline and the enforced one",
        why=(
            "the body announces this much more than it enforces so its own bound wins the race "
            "the announcement starts, and two module contracts quote the margin as the number a "
            "future agent reads instead of the tree, so retuning the constant alone would leave "
            "both of them describing an ordering the code no longer has (ADR-0024)"
        ),
        sites=(Site(RETRY_PLAN, "ANNOUNCED_DEADLINE_GRACE_MS"),),
        mentions=(
            Mention(BODY_CORE_DOC, "`ANNOUNCED_DEADLINE_GRACE_MS = {value}`"),
            Mention(BODY_RPC_DOC, "`ANNOUNCED_DEADLINE_GRACE_MS` ({value} ms)"),
        ),
    ),
    Constant(
        label="the subagent memory budget's shipped default",
        why=(
            "one compose file spells this number four times, once as the soft budget the "
            "admission scheduler is given and twice as the hard cgroup cap on the container "
            "running what it admits, so retuning the brain's field alone would cap that "
            "container at the old number while the scheduler admitted against the new one, "
            "which is the failure the resource governance exists to prevent (ADR-0012)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_MEM_BUDGET_GB"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-{value}}"'),
            Mention(
                SUBAGENTS_COMPOSE,
                '"${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-{value}}g"',
                occurrences=2,
                spelling=Spelling.WHOLE,
            ),
            Mention(SUBAGENTS_COMPOSE, "MEM_BUDGET_GB {value})"),
            Mention(SUBAGENTS_COMPOSE, "under the {value} GB budget", spelling=Spelling.WHOLE),
        ),
    ),
    Constant(
        label="the subagent CPU budget's shipped default",
        why=(
            "the same file spells this number three times, once as the soft budget the admission "
            "scheduler is given and once as the hard `cpus` cap on the container running what it "
            "admits, so retuning the brain's field alone would hand that container fewer cores "
            "than the spawns it is serving were charged against, which is the memory budget's "
            "failure in the other dimension and reads as a tier that got slow (ADR-0012)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_CPU_BUDGET"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_CPU_BUDGET:-{value}}"', occurrences=2),
            Mention(SUBAGENTS_COMPOSE, "CPU_BUDGET {value},"),
        ),
    ),
    Constant(
        label="the subagent VRAM ask's shipped default",
        why=(
            "the placer fit-tests this ask against the headroom left beside the resident cortex "
            "and the compose stack spells the measured number into every container it starts, so "
            "a field above the stack's refuses placements the card has room for and one below it "
            "admits a spawn onto room the tier then overruns (ADR-0012 measured-ask addendum)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_VRAM_GB"),),
        # The passthrough, and the sentence that records what was measured: an ask retuned without
        # that sentence leaves the file claiming a margin over a peak it no longer has.
        mentions=(
            Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_VRAM_GB:-{value}}"'),
            Mention(SUBAGENTS_COMPOSE, "{value} GiB sits"),
        ),
    ),
    Constant(
        label="the subagent CPU ask's shipped default",
        why=(
            "the scheduler charges this per spawn against the CPU budget above, so the two "
            "declarations decide together how many subagents run at once, and a stack that ships "
            "one number while the brain defaults to another admits a different count than the "
            "server's slots were sized for (ADR-0012)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_CPUS"),),
        mentions=(Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_CPUS:-{value}}"'),),
    ),
    Constant(
        label="the subagent memory ask's shipped default",
        why=(
            "the same charge in the other dimension, measured on the shipped entry and spelled "
            "both in the stack that ships it and in the sentence recording the measurement, so a "
            "field under the stack's admits more spawns than the container's own memory cap can "
            "hold, which is the unsafe direction (ADR-0012)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_MEMORY_GB"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_MEMORY_GB:-{value}}"'),
            Mention(SUBAGENTS_COMPOSE, "-> {value} memory ask"),
        ),
    ),
    Constant(
        label="the log rendering both brain processes ship with",
        why=(
            "the core declares which rendering a process entry installs when its env names "
            "none, and each compose service spells that same name as its own substitution "
            "default, so a renamed rendering would leave every composed deployment asking for "
            "one this build no longer carries and failing at startup"
        ),
        sites=(Site(LOG_FORMAT, "PLAIN_FORMAT"),),
        mentions=(
            Mention(BASE_COMPOSE, "${CORTEX_LOG_FORMAT:-{value}}"),
            Mention(GPU_COMPOSE, '"${CORTEX_MODELHOST_LOG_FORMAT:-{value}}"'),
        ),
    ),
)
