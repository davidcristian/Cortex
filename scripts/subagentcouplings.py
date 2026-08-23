"""The couplings around the subagent tier: what a spawn is charged, what its container gets, and
how long one may run.

One of the data files `crosscheck.py` reads as a single registry, split off `shippedcouplings.py`
when the compose survey pushed that file past the 300-line cap. The seam it fell on is the one its
own comment had already drawn: five knobs declared in one module and restated in one compose file,
two soft admission budgets each with a hard cgroup twin and the three numbers one spawn is charged.
They are one family and the failure is one failure, a container sized against a number the
scheduler is not admitting against, or a deployment charging a spawn something other than what the
shipped stack measured.

Nothing in the scan asks which file an entry sits in, so a coupling moves house without the gate
noticing; what a file buys is a reader who can hold one subject at a time.
"""

from couplings import Constant, Mention, Site, Spelling

SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"
SUBAGENTS_CORE = "brain/packages/core/src/cortex_core/subagents.py"
SUBAGENTS_SCHEDULER = "brain/packages/core/src/cortex_core/scheduler.py"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"
CORE_DOC = "docs/modules/brain-core.md"
INFERENCE_DOC = "docs/modules/brain-inference.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"

SUBAGENT_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the delegated run's shipped deadline",
        why=(
            "the deadline on a whole delegated run is declared in the core module the runner "
            "spends it from, quoted to an operator by the delegation runbook as the number a "
            "run is stopped at, quoted again by the tool runbook as the bound one tool call has "
            "to fit inside, and restated in the module contract a future agent reads instead of "
            "the tree, so retuning the declaration alone would leave three documents claiming a "
            "number no run is given (ADR-0005 total-cap addendum, ADR-0009 ordering addendum)"
        ),
        sites=(Site(SUBAGENTS_CORE, "DEFAULT_SUBAGENT_RUN_TIMEOUT_S"),),
        # Two runbooks write the number the way an operator says it out loud, a whole count of
        # seconds, and the module contract writes the field's own declaration, which carries the
        # point the float is declared with. So the entry re-spells twice and holds the written
        # form once, which is what keeps a re-spelling from quietly agreeing with another number.
        mentions=(
            Mention(
                SUBAGENTS_RUNBOOK,
                "`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` (default {value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(
                TOOLS_RUNBOOK,
                "`CORTEX_SUBAGENTS_RUN_TIMEOUT_S` (default {value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(ORCHESTRATOR_DOC, "`run_timeout_s: float = {value}`"),
        ),
    ),
    Constant(
        label="the stall ceiling's shipped default",
        why=(
            "the bound on how long a delegated stream may send nothing is declared in the "
            "config module the adapter builds its read timeout from, quoted to an operator by "
            "the delegation runbook as the gap a spawn is failed on, restated in the "
            "orchestrator contract as the field's own default, cited by the inference contract "
            "as the CPU pool's half of the two stall ceilings that adapter carries, and asserted "
            "as the lower end of an ordering by the core module declaring the run deadline that "
            "has to clear it, so retuning the declaration alone would leave three documents and "
            "one comment quoting a ceiling no stream is held to (ADR-0005 stall-ceiling "
            "addendum, ADR-0009 ordering addendum)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_STALL_TIMEOUT_S"),),
        # The two entries above with the numbers changed, and one document more. The runbook, the
        # inference contract and the ordering comment write the number the way it is said out
        # loud, a whole count of seconds; the orchestrator contract writes the field's own
        # declaration, so the point the float is declared with is held once and the entry keeps a
        # faithful reading beside three lossy ones.
        #
        # Two kinds stay out on rules already settled. The compose override names this env var in
        # its knob list and deliberately states no number, saying the brain's own default is left
        # alone, so there is nothing there to hold. And the orchestrator unit suite asserts this
        # default directly, which runs on every commit and holds itself. The resident tier's own
        # `stall_timeout_s` is a different constant that shares the field name and not the value,
        # 120.0 in `config.py`, which is why this entry is written by name rather than by number.
        mentions=(
            Mention(
                SUBAGENTS_RUNBOOK,
                "`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` (default {value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(
                INFERENCE_DOC,
                "`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` {value} s for the CPU pool",
                spelling=Spelling.WHOLE,
            ),
            Mention(SUBAGENTS_CORE, "the pool's {value} s", spelling=Spelling.WHOLE),
            Mention(ORCHESTRATOR_DOC, "`stall_timeout_s: float = {value}`"),
        ),
    ),
    Constant(
        label="the admission wait's shipped default",
        why=(
            "the bound on how long a spawn may queue for room is declared in the core module the "
            "scheduler defaults from, quoted to an operator by the delegation runbook as the "
            "wait the refusal names, restated in the two module contracts a future agent reads "
            "instead of the tree, and asserted as the upper end of an ordering by the sibling "
            "module declaring the run deadline that has to sit under it, so retuning the "
            "declaration alone would leave four places quoting a bound no spawn is given "
            "(ADR-0012 bounded-admission-wait addendum)"
        ),
        sites=(Site(SUBAGENTS_SCHEDULER, "DEFAULT_ADMISSION_WAIT_S"),),
        # The deadline's entry above with the numbers changed, and one shape more. The runbook and
        # the sibling module write the number the way it is said out loud, a whole count of
        # seconds; the two module contracts write the declaration itself, one restating the
        # field and one the constant, so both carry the point the float is declared with and the
        # entry keeps a faithful reading beside the two lossy ones.
        #
        # What is deliberately out is the arithmetic under the value rather than the value. Four
        # places say this bound is twice 1800 s and four times 900 s; those are consequences of
        # the wait and of a measured batch, and a needle over one would tie this constant to a
        # measurement, reddening when the measurement moved. The ADR index's own summary is out
        # on the rule that keeps every decision record out: it says what a dated addendum
        # decided, which stays true after the default moves. And the two unit suites asserting
        # this default run on every commit, so they hold themselves.
        mentions=(
            Mention(
                SUBAGENTS_RUNBOOK,
                "`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` (default {value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(SUBAGENTS_CORE, "its {value} s admission wait", spelling=Spelling.WHOLE),
            Mention(ORCHESTRATOR_DOC, "`admission_wait_s: float = {value}`"),
            Mention(CORE_DOC, "`DEFAULT_ADMISSION_WAIT_S` is {value},"),
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
)
