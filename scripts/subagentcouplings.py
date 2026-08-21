"""The couplings around the subagent tier: what a spawn is charged, and what its container gets."""

from couplings import Constant, Mention, Site, Spelling

SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"

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
)
