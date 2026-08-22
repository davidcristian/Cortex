"""The couplings around a shipped number: one tree declares it, and other files restate it.

One of the data files `crosscheck.py` reads as a single registry, split off `seamcouplings.py`
along the line that file's own second paragraph had been drawing since the deadlines arrived: the
entries there tie two trees whose code must hold the same value and neither of which can import the
other's, and the entries here cross a boundary of the same kind that is not a language. A default
the brain declares once, the compose stack spelling it again as a shell substitution, the container
limit that is its hard twin, the runbook quoting it to an operator as the shipped number, and the
module contract a future agent reads instead of the tree. Retuning the declaration alone leaves
every composed deployment running the old number and every reader told the old one, with nothing
saying so, which is the same drift with a different far side.

What is left here after the compose survey is **the brain container's own env**: the numbers and
the names the always-on service and its body override ship. The subagent tier's budgets moved to
`subagentcouplings.py` and the model-host sidecar's tiers to `modelhostcouplings.py`, each when
this file reached the 300-line cap, and each on a seam that was already a paragraph in it.

An ADR is deliberately not among those far sides. It records what was decided on a date and must go
on saying that after the number moves, where a runbook and a module contract describe what the tree
does now and are wrong the moment it changes. The same test settles every other far side outside
`docker/` (ADR-0029's compose-default survey addendum): a sentence that becomes **wrong** when the
value moves is a far side, and one that becomes **history** is not.

Two of the paths below are spelled in `seamcouplings.py` too, the base compose file and the body
client, each registered on both sides of that line for different values. The duplication is safe
rather than merely tolerated: a path that drifts in one file names something the scan cannot read,
and an unreadable place is a fault here and never a skip.
"""

from couplings import Constant, Mention, Site, Spelling

BASE_COMPOSE = "docker/docker-compose.yml"
BODY_COMPOSE = "docker/docker-compose.body.yml"
GPU_COMPOSE = "docker/docker-compose.gpu.yml"
IMAGES = "brain/packages/core/src/cortex_core/images.py"
LOG_FORMAT = "brain/packages/core/src/cortex_core/log_format.py"
BODY_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_body.py"
INFERENCE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
SCHEDULE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_schedule.py"
SCHEDULE_TIME = "brain/packages/core/src/cortex_core/schedule_time.py"
TOOLS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_tools.py"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_CORE_DOC = "docs/modules/body-core.md"
BODY_RPC_DOC = "docs/modules/body-rpc.md"
RETRY_PLAN = "body/crates/core/src/retry/plan.rs"
GPU_RUNBOOK = "docs/runbooks/llamacpp-gpu.md"
SCHEDULING_RUNBOOK = "docs/runbooks/scheduling.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"
TOOLS_CORE_DOC = "docs/modules/brain-core.md"
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
        # The delegation runbook writes it the way an operator says a duration out loud, a whole
        # count of seconds, where the tool runbook quotes the field's own default; both are the
        # same number and neither can be rendered from the other's text (ADR-0009 ordering
        # addendum, which put the bound in front of a reader tuning the run that contains it).
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
    # The two deadlines on the brain->body seam, and the first decimals the registry held. Each is
    # declared once, in the adapter that spends it, and spelled again in four places that must move
    # with it: the compose default every deployment boots on, the two runbooks that quote it to an
    # operator, and the module contract a future agent reads instead of the tree. The value is
    # compared as the digits it is written with rather than as a number, so a site retyped as `5`
    # does not quietly agree with a stack still substituting `5.0` (see `values.py`). Each runbook
    # template carries the variable's own name so it pins the row that names it, a bare `10.0`
    # being a number any other row could satisfy.
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
            "the compose stack ships this edge into every container and two runbooks quote it as "
            "the brain half of the measured legibility pair, so retuning the field alone would "
            "leave every deployment asking for the old edge while the encoder was sized for the "
            "new one (ADR-0029 legibility addendum)"
        ),
        sites=(Site(BODY_CONFIG, "DEFAULT_CAPTURE_MAX_EDGE"),),
        # The last mention is the GPU override's own comment, which argues for the token budget by
        # naming this edge, in the same `VAR=value` shape the runbook above it already writes. A
        # comment is no new form and no new spelling, only another place a whole value appears; a
        # far side is a sentence that becomes wrong, and this one does, the pair being what each
        # number is for (ADR-0029 comment addendum).
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CAPTURE_MAX_EDGE:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CAPTURE_MAX_EDGE` | brain | `{value}` |"),
            Mention(GPU_RUNBOOK, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(GPU_COMPOSE, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
        ),
    ),
    Constant(
        label="the capture byte budget's shipped default",
        why=(
            "the brain's budget defaults to the body's own ceiling, and the stack spells that "
            "number again while the vision runbook quotes it as the shipped budget, so a "
            "tightened ceiling with the substitution left alone would ask every deployment for "
            "more bytes than either end now allows (ADR-0029)"
        ),
        sites=(Site(IMAGES, "MAX_IMAGE_BYTES"),),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_MAX_IMAGE_BYTES:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_MAX_IMAGE_BYTES` | brain | `{value}` |"),
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
    Constant(
        label="the grace between the announced deadline and the enforced one",
        why=(
            "the body announces this much more than it enforces so its own bound wins the race "
            "the announcement starts, and two module contracts quote the margin as the number a "
            "future agent reads instead of the tree, so retuning the constant alone would leave "
            "both of them describing an ordering the code no longer has (ADR-0024)"
        ),
        sites=(Site(RETRY_PLAN, "ANNOUNCED_DEADLINE_GRACE_MS"),),
        # The contracts spell it in the two shapes their sentences need: the core's names the
        # constant it is reading out, the adapter's spends it as the millisecond value a reader
        # compares against the deadlines beside it. Both carry a unit or a name, a bare 250 being
        # a number the probe deadline on the same page would satisfy.
        mentions=(
            Mention(BODY_CORE_DOC, "`ANNOUNCED_DEADLINE_GRACE_MS = {value}`"),
            Mention(BODY_RPC_DOC, "`ANNOUNCED_DEADLINE_GRACE_MS` ({value} ms)"),
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
