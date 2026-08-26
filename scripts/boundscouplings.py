"""The couplings around the bounds one delegated run stands between: how long the whole run may
take, how far any one completion may decode, how long its stream may say nothing, and how long a
spawn may queue for room before the refusal names the wait.
"""

from couplings import Constant, Mention, Site, Spelling

SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"
SUBAGENTS_CORE = "brain/packages/core/src/cortex_core/subagents.py"
SUBAGENTS_SCHEDULER = "brain/packages/core/src/cortex_core/scheduler.py"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"
TOOLS_RUNBOOK = "docs/runbooks/tools-mcp.md"
CORE_DOC = "docs/modules/brain-core.md"
INFERENCE_DOC = "docs/modules/brain-inference.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"

BOUNDS_COUPLINGS: tuple[Constant, ...] = (
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
)
