"""The couplings around the bounds one delegated run stands between: how long the whole run may
take, how far any one completion may decode, how long its stream may say nothing, and how long a
spawn may queue for room before the refusal names the wait.

One of the data files `crosscheck.py` reads as a single registry, and the eleventh part to arrive.
It was split off `subagentcouplings.py` when the tier's reasoning-off pair brought that file to two
lines under the 300-line cap, on the seam its sibling's own name had been drawing since the first
of these entries landed: `subagentcouplings` is the tier's admission budgets against the container
limits that are their hard twins, which is a claim about what a container is given, and these four
are a claim about what one run is allowed.

The same seam is visible in where each entry's far sides are. Every value here is declared in a
brain module and restated by a runbook an operator reads and by a module contract a future agent
reads instead of the tree, and not one of them is spelled in a compose file, because the stack
ships none of these numbers and so can drift from none of them. The four are one family and the
failure is one failure, a run stopped at a bound some document promises it is not. They are also
ordered against each other, the stall ceiling under the run deadline and the run deadline under the
admission wait, an ordering the core module declaring that deadline states in the comment beside
it and so is a far side of both its neighbours.

`SUBAGENTS_CONFIG` is written here and in `subagentcouplings.py` both, which is safe for the reason
this scan is built on: a path that drifts in one of them names something the scan cannot read, and
an unreadable place is a fault here and never a skip.

Nothing in the scan asks which file an entry sits in, so the move cost the gate nothing; a file of
its own gives a reader one subject at a time.
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
        # The entry above with the numbers changed and nothing re-spelled: a token count is an int
        # on every side, so both mentions write it the way the declaration does and this entry
        # needs no lossy reading beside them.
        #
        # Two kinds stay out, on the rules the siblings below already settled. The arithmetic under
        # the value is out: four places say the cap is about five times the longest reply this tier
        # was measured writing, which is a consequence of a measurement, and a needle over it would
        # fail this constant whenever the measurement moved. And the core suite pins the cap by
        # its literal where it asserts the refusal's own wording, which runs on every commit and so
        # holds itself.
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
        # measurement, failing when the measurement moved. The ADR index's own summary is out
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
)
