"""The couplings around the subagent tier: the budgets a spawn is charged, the limits its
container is given, and the count that turns its thinking off.
"""

from couplings import Constant, Form, Mention, Site

SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
ROSTER_COMPOSE = "docker/docker-compose.subagents-roster.yml"
MODELHOST_CONFIG = "brain/packages/model_manager/src/cortex_model_manager/config.py"
SUBAGENTS_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py"
FLAG_CHECK = "scripts/subagentflags.py"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"

SUBAGENT_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the subagent memory budget's shipped default",
        why=(
            "the subagents compose file writes this number four times, once as the soft budget "
            "the admission scheduler is given and twice as the hard cgroup cap on the container "
            "running what it admits, and the roster file caps its own server the same way, so "
            "retuning the brain's field alone would cap those containers at the old number while "
            "the scheduler admitted against the new one, which is the failure the resource "
            "governance exists to prevent (ADR-0012)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_MEM_BUDGET_GB"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-{value}}"'),
            Mention(
                SUBAGENTS_COMPOSE,
                '"${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-{value}}g"',
                occurrences=2,
                form=Form.WHOLE,
            ),
            Mention(SUBAGENTS_COMPOSE, "MEM_BUDGET_GB {value})"),
            Mention(SUBAGENTS_COMPOSE, "under the {value} GB budget", form=Form.WHOLE),
            Mention(
                ROSTER_COMPOSE,
                '"${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-{value}}g"',
                occurrences=2,
                form=Form.WHOLE,
            ),
        ),
    ),
    Constant(
        label="the subagent CPU budget's shipped default",
        why=(
            "the subagents compose file writes this number as the soft budget the admission "
            "scheduler is given, as the hard `cpus` cap on the container running what it admits "
            "and as that server's `--threads`, and the roster file writes the cap and the thread "
            "count again for its own server, so retuning the brain's field alone would hand those "
            "containers fewer cores than the spawns they serve were charged against, which is the "
            "memory budget's failure in the other dimension and reads as a tier that got slow "
            "(ADR-0012, and ADR-0004 decision 12 for the count)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_CPU_BUDGET"),),
        mentions=(
            Mention(SUBAGENTS_COMPOSE, '"${CORTEX_SUBAGENTS_CPU_BUDGET:-{value}}"', occurrences=3),
            Mention(SUBAGENTS_COMPOSE, "CPU_BUDGET {value},"),
            Mention(ROSTER_COMPOSE, '"${CORTEX_SUBAGENTS_CPU_BUDGET:-{value}}"', occurrences=2),
            Mention(
                SUBAGENTS_COMPOSE,
                '- "--threads"\n      - "${CORTEX_SUBAGENTS_CPU_BUDGET:-{value}}"',
            ),
            Mention(
                ROSTER_COMPOSE,
                '- "--threads"\n      - "${CORTEX_SUBAGENTS_CPU_BUDGET:-{value}}"',
            ),
        ),
    ),
    Constant(
        label="the subagent VRAM ask's shipped default",
        why=(
            "the placer fit-tests this ask against the headroom left beside the resident cortex "
            "and the compose stack writes the measured number into every container it starts, so "
            "a field above the stack's refuses placements the card has room for and one below it "
            "admits a spawn onto room the tier then overruns (ADR-0012 decision 14)"
        ),
        sites=(Site(SUBAGENTS_CONFIG, "DEFAULT_VRAM_GB"),),
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
            "the same charge in the other dimension, measured on the shipped entry and written "
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
            "rather than a short one, and three places write it: the argv the model host starts "
            "its own hosted subagent tier with, the value the flag check requires of every "
            "subagent server the compose stack starts, and the subagent runbook, which both "
            "states the pair to check on any tier's argv and hands an operator a `docker run` "
            "that starts a server with it. Retuning one leaves two halves of one tier under two "
            "answers to what thinking costs, and an operator bringing up a server the shipped "
            "stack would not (ADR-0049)"
        ),
        sites=(Site(MODELHOST_CONFIG, "_NO_REASONING_BUDGET"),),
        mentions=(
            Mention(FLAG_CHECK, 'Flag("--reasoning-budget", "{value}")'),
            Mention(SUBAGENTS_RUNBOOK, "`--reasoning-budget {value}`"),
            Mention(SUBAGENTS_RUNBOOK, "\n  --reasoning-budget {value}\n"),
        ),
    ),
)
