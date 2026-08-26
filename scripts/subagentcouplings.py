"""The couplings around the subagent tier: what a spawn is charged, what its container gets, how
long one may run, and the reasoning-off pair every server in it starts with.
"""

from couplings import Constant, Mention, Site, Spelling

SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
ROSTER_COMPOSE = "docker/docker-compose.subagents-roster.yml"
MODELHOST_CONFIG = "brain/packages/model_manager/src/cortex_model_manager/config.py"
SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"
SUBAGENTS_CORE = "brain/packages/core/src/cortex_core/subagents.py"
SUBAGENTS_SCHEDULER = "brain/packages/core/src/cortex_core/scheduler.py"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"
CORE_DOC = "docs/modules/brain-core.md"
INFERENCE_DOC = "docs/modules/brain-inference.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"

REASONING_OFF_PAIR = (
    '- "--chat-template-kwargs"\n'
    "      - '{\"enable_thinking\": false}'\n"
    '      - "--reasoning-budget"\n'
    '      - "{value}"'
)

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
        label="the delegated completion's shipped token cap",
        why=(
            "the cap on how far any one completion of a delegated run may decode is declared in "
            "the core module the attempt builds its generation bounds from, quoted to an operator "
            "by the delegation runbook as the count a completion is cut at, and restated in the "
            "orchestrator contract as the field's own default, so retuning the declaration alone "
            "would leave two documents quoting a cap no completion is held to. It is the other "
            "half of the value the entry above holds, the two shipping together as one "
            "`AttemptBounds`, and it was the only one of the four bounds around a delegated run "
            "this registry did not hold (ADR-0005 total-cap addendum)"
        ),
        sites=(Site(SUBAGENTS_CORE, "DEFAULT_SUBAGENT_MAX_TOKENS"),),
        mentions=(
            Mention(SUBAGENTS_RUNBOOK, "`CORTEX_SUBAGENTS_MAX_TOKENS` (default {value})"),
            Mention(ORCHESTRATOR_DOC, "`max_tokens: int = {value}`"),
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
        label="the subagent tier's reasoning-off flag pair",
        why=(
            "every subagent server this repo starts carries both `--chat-template-kwargs` and "
            "`--reasoning-budget 0`, because neither flag alone covers both lineup families: the "
            "kwarg is what a Qwen chat template reads and what the gemma-4-E* templates ignore, "
            "and the budget is what reaches the constrained request shape every tool-less "
            "subagent decodes into the fixed envelope. A server started with half the pair spends "
            "its whole token cap on a trace no reader ever sees and answers a cap refusal, which "
            "is a defect whose only symptom is a slow subagent (ADR-0005 thinking-lever addendum)"
        ),
        sites=(Site(MODELHOST_CONFIG, "_NO_REASONING_BUDGET"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, REASONING_OFF_PAIR),
            Mention(ROSTER_COMPOSE, REASONING_OFF_PAIR),
        ),
    ),
)
