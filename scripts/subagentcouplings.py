"""The couplings around the subagent tier's container: what a spawn is charged, what the container
running it is given, and the count that says its servers do no thinking at all.

One of the data files `crosscheck.py` reads as a single registry, split off `shippedcouplings.py`
when the compose survey pushed that file past the 300-line cap. The seam it fell on is the one its
own comment had already drawn: five knobs declared in one module and restated in one compose file,
two soft admission budgets each with a hard cgroup twin and the three numbers one spawn is charged.
They are one family and the failure is one failure, a container sized against a number the
scheduler is not admitting against, or a deployment charging a spawn something other than what the
shipped stack measured.

The four bounds one delegated run stands between arrived here afterwards and left the same way,
to `boundscouplings.py`, when the reasoning-off pair below brought this file to two lines under the
cap. They were a claim about what one run is allowed where everything left is a claim about what
the container serving it gets, and every one of them is restated by a document rather than by the
stack, so the split is visible in the paths as well as in the labels.

The reasoning-off entry below is narrower than it was, and deliberately. It used to render the
tier's flag pair as four compose list items and require them in each of the two servers it could
name, which is a claim about two files where the claim worth making is about every server the
stack starts. `flagcheck.py` derives that set and holds the pair over all of it, so what stays
here is the value under one half of the pair, tied to the sidecar that declares it: a set is a
rule's to enforce, and a number spelled in two trees is this registry's.

Nothing in the scan asks which file an entry sits in, so a coupling moves house without the gate
noticing; what a file buys is a reader who can hold one subject at a time.
"""

from couplings import Constant, Mention, Site, Spelling

SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
MODELHOST_CONFIG = "brain/packages/model_manager/src/cortex_model_manager/config.py"
SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"
FLAG_GATE = "scripts/flagcheck.py"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"

SUBAGENT_COUPLINGS: tuple[Constant, ...] = (
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
        label="the subagent tier's reasoning-off budget",
        why=(
            "the count under `--reasoning-budget` is what says a narrow subtask wants no thought "
            "rather than a short one, and three places spell it: the argv the model host starts "
            "its own hosted subagent tier with, the value the flag gate requires of every "
            "subagent server the compose stack starts, and the subagent runbook, which both "
            "states the pair to check on any tier's argv and hands an operator a `docker run` "
            "that starts a server with it. Retuning one leaves two halves of one tier under two "
            "answers to what thinking costs, and an operator bringing up a server the shipped "
            "stack would not (ADR-0005 switch-is-advisory addendum)"
        ),
        # The one place a language this scan reads declares it: the hosted GPU tier's argv, whose
        # count was hoisted out of `_REASONING_OFF` to be readable at all. The entry sits here
        # rather than beside that sidecar's tier settings because what it holds is the subagent
        # tier's servers. The flag gate now reads that same declaration and requires the pair of
        # it, so this entry's own two Python places overlap with a rule; what it keeps that no
        # rule reaches is the runbook below, and the count is worth pinning from both directions.
        sites=(Site(MODELHOST_CONFIG, "_NO_REASONING_BUDGET"),),
        # The two compose needles this entry used to carry are gone, and that is the whole point.
        # They rendered the pair as four list items and required it in each of the two servers
        # this file could name, which held those two files and said nothing about a third.
        # `flagcheck.py` derives that set from the stack's own wiring and argv and holds every
        # server in it to the pair, so the co-occurrence now lives in a rule that can express it
        # over a set, and what stays here is the value under one half of it.
        #
        # The runbook is the far side no gate over compose could reach: its `docker run` starts a
        # server by hand, outside any stack, and its prose tells a deployment adding a server of
        # its own what to put on the argv. Both go on saying zero the day the tier stops shipping
        # one. The two spellings are separate needles because they are separate shapes, the fenced
        # command carrying its own indentation and the prose its backticks, and neither is pinned
        # to a count: the prose says this three times in three arguments, and a paragraph rewritten
        # to say it twice is an edit rather than a defect.
        mentions=(
            Mention(FLAG_GATE, 'Flag("--reasoning-budget", "{value}")'),
            Mention(SUBAGENTS_RUNBOOK, "`--reasoning-budget {value}`"),
            Mention(SUBAGENTS_RUNBOOK, "\n  --reasoning-budget {value}\n"),
        ),
    ),
)
