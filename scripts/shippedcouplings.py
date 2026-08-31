"""The couplings around a shipped number: one tree declares it, and other files restate it."""

from couplings import Constant, Mention, Site, Spelling

BASE_COMPOSE = "docker/docker-compose.yml"
GPU_COMPOSE = "docker/docker-compose.gpu.yml"
LOG_FORMAT = "brain/packages/core/src/cortex_core/log_format.py"
SCHEDULE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_schedule.py"
SCHEDULE_TIME = "brain/packages/core/src/cortex_core/schedule_time.py"
TOOLS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_tools.py"
BODY_CORE_DOC = "docs/modules/body-core.md"
BODY_RPC_DOC = "docs/modules/body-rpc.md"
RETRY_PLAN = "body/crates/core/src/retry/plan.rs"
SEAM_CALL = "body/crates/rpc/src/call.rs"
RETRY_GAP = "body/crates/core/src/retry/gap.rs"
BODY_APP_DOC = "docs/modules/body-app.md"
OVERLAY_RUNBOOK = "docs/runbooks/body-overlay.md"
SCHEDULING_RUNBOOK = "docs/runbooks/scheduling.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"
TOOLS_CORE_DOC = "docs/modules/brain-core.md"

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
        label="the salience rule the stack ships",
        why=(
            "the same knob's other half: the base compose file names which rule a loop runs "
            "under and the runbook tells an operator which one is running, so a retuned default "
            "with the substitution left alone would ship the old rule to every deployment while "
            "the field claimed the new one (ADR-0009 salience addendum)"
        ),
        sites=(Site(TOOLS_CONFIG, "DEFAULT_SALIENCE"),),
        mentions=(
            Mention(BASE_COMPOSE, "${CORTEX_TOOLS_SALIENCE:-{value}}"),
            Mention(TOOLS_RUNBOOK, "`CORTEX_TOOLS_SALIENCE`, default `{value}`"),
        ),
    ),
    Constant(
        label="the tool call's shipped bound",
        why=(
            "the deadline one call on a tool sidecar runs under is declared in the core module "
            "that spends it, substituted into every container the base compose file starts, "
            "quoted to an operator by two runbooks, as the number a wedged sidecar fails at and "
            "as the bound one call inside a delegated run has to fit under, and restated in the "
            "module contract a future agent reads instead of the tree, so retuning the "
            "declaration alone would leave every deployment on the old bound with three "
            "documents claiming the new one (ADR-0009 bound addendum)"
        ),
        sites=(
            Site(
                "brain/packages/core/src/cortex_core/tool_deadline.py",
                "DEFAULT_TOOL_CALL_TIMEOUT_S",
            ),
        ),
        mentions=(
            Mention(BASE_COMPOSE, "${CORTEX_TOOLS_CALL_TIMEOUT_S:-{value}}"),
            Mention(TOOLS_RUNBOOK, "`CORTEX_TOOLS_CALL_TIMEOUT_S` (default `{value}`"),
            Mention(
                SUBAGENTS_RUNBOOK,
                "`CORTEX_TOOLS_CALL_TIMEOUT_S` (default {value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(TOOLS_CORE_DOC, "`DEFAULT_TOOL_CALL_TIMEOUT_S = {value}`"),
        ),
    ),
    Constant(
        label="the longest a turn may be silent before its first event",
        why=(
            "two module contracts and the overlay runbook quote this as the number a reader acts "
            "on, one telling a future agent what the plan ships and the other telling an operator "
            "how long a turn that never starts will hang before it settles, so retuning the "
            "constant alone would leave all three describing a bound the body no longer holds "
            "(ADR-0024 idle-gap addendum)"
        ),
        sites=(Site(RETRY_GAP, "DEFAULT_TURN_FIRST_GAP_MS"),),
        mentions=(
            Mention(BODY_CORE_DOC, "`DEFAULT_TURN_FIRST_GAP_MS = {value}`"),
            Mention(BODY_APP_DOC, "`DEFAULT_TURN_FIRST_GAP_MS = {value}`"),
            Mention(OVERLAY_RUNBOOK, "(default {value}, ten minutes)"),
        ),
    ),
    Constant(
        label="the longest a turn may be silent between two of its events",
        why=(
            "the same three readers carry this one, and it is the number that decides whether a "
            "delegated batch is allowed to finish: a contract or a runbook still quoting the old "
            "one would tell a reader a turn survives a silence the body now ends "
            "(ADR-0024 idle-gap addendum)"
        ),
        sites=(Site(RETRY_GAP, "DEFAULT_TURN_IDLE_GAP_MS"),),
        mentions=(
            Mention(BODY_CORE_DOC, "`DEFAULT_TURN_IDLE_GAP_MS = {value}`"),
            Mention(BODY_APP_DOC, "`DEFAULT_TURN_IDLE_GAP_MS = {value}`"),
            Mention(OVERLAY_RUNBOOK, "(default {value}, two hours)"),
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
        label="the longest deadline the seam is willing to announce",
        why=(
            "the grace above is only a margin while the header can carry the announcement in "
            "milliseconds; one rung higher the unit is a whole second and the announcement arms "
            "tonic's own clock under the bound the core enforces, so the adapter rejects it "
            "there, and its contract quotes the rung as the number a future agent reads instead "
            "of the tree (ADR-0024 unit-ladder addendum)"
        ),
        sites=(Site(SEAM_CALL, "MAX_ANNOUNCED_DEADLINE_MS"),),
        # The contract spends it as the millisecond count beside the human scale a reader thinks
        # in, the way the gap knobs above are quoted, since eight bare digits name nothing on a
        # page that also carries the header's own 8-digit width.
        mentions=(
            Mention(BODY_RPC_DOC, "`MAX_ANNOUNCED_DEADLINE_MS` ({value} ms, about 27.8 hours)"),
        ),
    ),
    # The two schedule knobs the base compose file restates, one a policy and one a zone. The zone
    # needs no hoisted constant: the core already names it, the settings field importing that name
    # rather than spelling a second `"UTC"`.
    Constant(
        label="whether a deployment ships a durable schedule store",
        why=(
            "the base compose file names the backend every deployment boots on and the "
            "scheduling runbook opens by stating it, so turning the shipped answer on in the "
            "field alone would leave every composed stack still running without a store while "
            "both the field and the reader believed otherwise (ADR-0025)"
        ),
        sites=(Site(SCHEDULE_CONFIG, "DEFAULT_SCHEDULE_BACKEND"),),
        mentions=(
            Mention(BASE_COMPOSE, "${CORTEX_SCHEDULE_BACKEND:-{value}}"),
            Mention(SCHEDULING_RUNBOOK, "(`CORTEX_SCHEDULE_BACKEND={value}`)"),
        ),
    ),
    Constant(
        label="the display zone every deployment renders in",
        why=(
            "the core names the zone a schedule datetime renders in when the deployment names "
            "none, and the base compose file spells that same key as its own substitution "
            "default, so a renamed key would leave every composed deployment asking for a zone "
            "the brain refuses at startup (ADR-0025 display addendum)"
        ),
        sites=(Site(SCHEDULE_TIME, "UTC_ZONE_NAME"),),
        mentions=(Mention(BASE_COMPOSE, "${CORTEX_SCHEDULE_TZ:-{value}}"),),
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
