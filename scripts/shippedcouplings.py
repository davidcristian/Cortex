"""The couplings around a shipped number: one tree declares it, and other files restate it.

One of the three data files `crosscheck.py` reads as a single registry, split off `seamcouplings.py`
along the line that file's own second paragraph had been drawing since the deadlines arrived: the
entries beside this one tie two trees whose code must hold the same value and neither of which can
import the other's, and the entries here cross a boundary of the same kind that is not a language.
A default the brain declares once, the compose stack spelling it again as a shell substitution, the
container limit that is its hard twin, the runbook quoting it to an operator as the shipped number,
and the module contract a future agent reads instead of the tree. Retuning the declaration alone
leaves every composed deployment running the old number and every reader told the old one, with
nothing saying so, which is the same drift with a different far side.

An ADR is deliberately not among those far sides. It records what was decided on a date and must go
on saying that after the number moves, where a runbook and a module contract describe what the tree
does now and are wrong the moment it changes.

Two of the paths below are spelled in `seamcouplings.py` too, the base compose file and the body
client, each registered on both sides of that line for different values. The duplication is safe
rather than merely tolerated: a path that drifts in one file names something the scan cannot read,
and an unreadable place is a fault here and never a skip.
"""

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
    # The five subagent knobs, all declared in one module and all restated in one compose file:
    # the two soft admission budgets, each with a hard cgroup twin, and the three numbers one
    # subagent's spawn is charged. They are one family and the failure is one failure, a container
    # sized against a number the scheduler is not admitting against, or a deployment charging a
    # spawn something other than what the shipped stack measured.
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
        # Four spends of one number, in the two spellings it has to be written in. The
        # environment passthrough and the comment claiming the twinning carry the digits the
        # field declares; docker's size suffix cannot, `8.0g` being a size it refuses, so the
        # two container limits and the sentence that counts admissions against them take the
        # whole spelling. Each template covers the whole of what it pins (the quotes around a
        # compose scalar, the paren closing the claim), a needle stopping at the substitution's
        # own `}` being satisfied by the size limits and leaving the passthrough free to drift.
        # The limits are counted because they are one set: memswap equal to memory is what
        # disables the container's swap, and one moving without the other re-enables it in
        # silence, which is a subagent that takes minutes per token and reads as a hang.
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
        # Three spends and no second spelling, unlike the memory budget above: docker's `cpus`
        # takes a float where its size suffix will not, so every place here writes the digits the
        # field declares. The passthrough and the cgroup limit render identically and are counted
        # as one set, being the twinning the comment beside them claims: one moving without the
        # other is the whole of what this entry reports.
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
