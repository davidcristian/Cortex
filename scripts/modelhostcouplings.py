"""The couplings around the model host: which tiers it runs, and how patiently it stops them.

One of the data files `crosscheck.py` reads as a single registry, split off `shippedcouplings.py`
when the compose survey pushed that file past the 300-line cap. The subject is one env surface:
`ModelHostConfig` and the supervisor beside it declare what a tier is served with, and one compose
override spells nearly every one of those answers again as a substitution default. Because the
override always sets the variable, the substitution is what a composed deployment actually runs and
the Python default is what it merely appears to run, so a retune on the Python side alone changes
nothing anywhere and says so nowhere. That is the drift these entries report.

Several of the numbers here were hidden inside `Field(...)` calls, which this scan cannot read; the
survey hoisted each into a module constant beside the field it defaults, which is the cost of a
registered coupling and is paid once (ADR-0029's compose-default survey addendum).
"""

from couplings import Constant, Mention, Site, Spelling

GPU_COMPOSE = "docker/docker-compose.gpu.yml"
SUBAGENTS_COMPOSE = "docker/docker-compose.subagents.yml"
ROSTER_COMPOSE = "docker/docker-compose.subagents-roster.yml"
ENGINE = "brain/packages/core/src/cortex_core/engine.py"
MODELHOST_CONFIG = "brain/packages/model_manager/src/cortex_model_manager/config.py"
SUPERVISOR = "brain/packages/model_manager/src/cortex_model_manager/supervisor.py"
SWAP_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_swap.py"
MODEL_MANAGER_DOC = "docs/modules/brain-model-manager.md"
GPU_RUNBOOK = "docs/runbooks/llamacpp-gpu.md"
SWAP_RUNBOOK = "docs/runbooks/model-swap.md"

MODELHOST_COUPLINGS: tuple[Constant, ...] = (
    # The two logical ids. Each is spent twice in the override, once as the sidecar's env and once
    # inside the healthcheck URL that asks whether that tier is ready, and the two are one set: a
    # renamed tier whose healthcheck still probes the old id reports a stack that never comes up.
    Constant(
        label="the resident tier's logical id",
        why=(
            "the brain addresses the cortex by this id and the sidecar answers under it, and the "
            "compose override both passes it and probes it in the healthcheck, so a rename in "
            "the core alone leaves the stack serving one id and asking after another (ADR-0004)"
        ),
        sites=(Site(ENGINE, "DEFAULT_CORTEX_MODEL"),),
        mentions=(Mention(GPU_COMPOSE, "${CORTEX_MODEL_CORTEX:-{value}}", occurrences=2),),
    ),
    Constant(
        label="the deep tier's logical id",
        why=(
            "two brain packages declare this id, the swap config that escalates to it and the "
            "sidecar config that hosts it, and the override passes and probes it as well, so all "
            "four have to be one word or a handoff addresses a tier nothing serves (ADR-0030)"
        ),
        sites=(
            Site(SWAP_CONFIG, "DEFAULT_BRAIN_MODEL"),
            Site(MODELHOST_CONFIG, "DEFAULT_BRAIN_MODEL"),
        ),
        mentions=(Mention(GPU_COMPOSE, "${CORTEX_MODEL_BRAIN:-{value}}", occurrences=2),),
    ),
    Constant(
        label="the cortex artifact the stack ships",
        why=(
            "the sidecar names the pick it starts when a deployment names none and the GPU "
            "runbook prints the same path as the shipped default, so a new pick landing in the "
            "config alone would leave every composed deployment loading the old GGUF (ADR-0004)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_CORTEX_FILE"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_MODEL_FILE_CORTEX:-{value}}"),
            Mention(GPU_RUNBOOK, "| `{value}` |"),
        ),
    ),
    Constant(
        label="how many layers a tier offloads",
        why=(
            "one number serves all three tiers and the override spells it again for the two it "
            "gives a layer count, so a deployment that decided to split a model across host and "
            "card in the config alone would still get every layer on the GPU (ADR-0004 addendum)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_NGL"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_NGL:-{value}}"),
            Mention(GPU_COMPOSE, "${CORTEX_NGL_BRAIN:-{value}}"),
            Mention(GPU_RUNBOOK, "`{value}` = all"),
        ),
    ),
    Constant(
        label="the resident tier's context window",
        why=(
            "the KV cache this sizes is the largest single piece of the cortex's VRAM, so a "
            "context retuned in the config while the override still substitutes the old one "
            "changes the budget nowhere and the documented budget everywhere (ADR-0004)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_CORTEX_CTX_SIZE"),),
        mentions=(Mention(GPU_COMPOSE, "${CORTEX_CTX_SIZE:-{value}}"),),
    ),
    Constant(
        label="the deep tier's context window",
        why=(
            "the same number in the other direction: the deep model is loaded only by evicting "
            "the others, so its context is what decides whether the handoff fits the card at "
            "all, and the stack's answer is the one a swap really runs (ADR-0030)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_BRAIN_CTX_SIZE"),),
        mentions=(Mention(GPU_COMPOSE, "${CORTEX_CTX_SIZE_BRAIN:-{value}}"),),
    ),
    # The two subagent-tier knobs the sidecar declares. Both are spelled in three compose files,
    # because the same variable configures the GPU-placed tier and the CPU llama-server the
    # subagent overrides start, and a deployment sets it once for all of them.
    Constant(
        label="a subagent tier's context window",
        why=(
            "three compose files substitute this one variable, the GPU-placed tier's and both "
            "CPU servers', so a retune in the sidecar config alone would leave every one of them "
            "serving the old window while the config claimed the new one (ADR-0010/0018)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_SUBAGENT_CTX_SIZE"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_SUBAGENT_CTX_SIZE:-{value}}"),
            Mention(SUBAGENTS_COMPOSE, "${CORTEX_SUBAGENT_CTX_SIZE:-{value}}"),
            Mention(ROSTER_COMPOSE, "${CORTEX_SUBAGENT_CTX_SIZE:-{value}}"),
        ),
    ),
    Constant(
        label="how many subagent slots a server holds",
        why=(
            "the same three files substitute the slot count, which is how many delegated runs a "
            "server serves at once and therefore what the admission budgets were sized against, "
            "so the config and the stack disagreeing is a tier queueing where it was measured "
            "not to (ADR-0010/0012)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_SUBAGENT_PARALLEL"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_SUBAGENTS_PARALLEL:-{value}}"),
            Mention(SUBAGENTS_COMPOSE, "${CORTEX_SUBAGENTS_PARALLEL:-{value}}"),
            Mention(ROSTER_COMPOSE, "${CORTEX_SUBAGENTS_PARALLEL:-{value}}"),
        ),
    ),
    Constant(
        label="how many tokens one picture may occupy",
        why=(
            "this is the model-host half of the measured legibility pair the brain's capture "
            "edge is the other half of, and both the override and the GPU runbook state it, so "
            "a budget retuned in the config alone would pay the edge's pixels for an encoder "
            "still refusing to spend tokens on them (ADR-0029 legibility addendum)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_IMAGE_MAX_TOKENS"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_IMAGE_MAX_TOKENS:-{value}}"),
            Mention(GPU_RUNBOOK, "`{value}` is the default, paired with"),
        ),
    ),
    Constant(
        label="what reads the card on the health route",
        why=(
            "the daemon reports free VRAM by running this binary and the override names it "
            "again, so a deployment that pointed the config at another path would still run the "
            "toolkit's own name and answer with no reading at all (ADR-0030)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_NVIDIA_SMI"),),
        mentions=(Mention(GPU_COMPOSE, "${CORTEX_MODELHOST_NVIDIA_SMI:-{value}}"),),
    ),
    # The three eviction deadlines, whose sum the brain's own control-plane timeout must clear.
    # Each is declared as a decimal and spent in three places: the override, which now spells the
    # point the constant carries so the two are one text, and two documents whose sentences read
    # `10 s` the way prose does. Those take the whole spelling, and the entry keeps the written
    # one at the compose mention, which is what `values.spelling_fault` requires of a re-spelling.
    Constant(
        label="the grace a child gets before it is killed",
        why=(
            "an eviction pays this whole grace when the child has a request in flight, and both "
            "the swap runbook and the module contract quote it as the cost to plan for, so a "
            "retune in the supervisor alone would leave every deployment paying the old wait "
            "and every reader told it (ADR-0030)"
        ),
        sites=(Site(SUPERVISOR, "DEFAULT_STOP_GRACE_S"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_MODELHOST_STOP_GRACE_S:-{value}}"),
            Mention(
                SWAP_RUNBOOK,
                "`CORTEX_MODELHOST_STOP_GRACE_S` ({value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(
                MODEL_MANAGER_DOC, "`DEFAULT_STOP_GRACE_S` ({value} s)", spelling=Spelling.WHOLE
            ),
        ),
    ),
    Constant(
        label="how long a killed child gets to be reaped",
        why=(
            "the second term of the sum the brain's control-plane deadline must clear, stated in "
            "the same runbook and the same contract, so a stack substituting one number while "
            "the supervisor waits another makes that documented pairing arithmetic nobody can "
            "check (ADR-0030)"
        ),
        sites=(Site(SUPERVISOR, "DEFAULT_REAP_TIMEOUT_S"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_MODELHOST_REAP_TIMEOUT_S:-{value}}"),
            Mention(
                SWAP_RUNBOOK,
                "`CORTEX_MODELHOST_REAP_TIMEOUT_S` ({value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(
                MODEL_MANAGER_DOC, "`DEFAULT_REAP_TIMEOUT_S` ({value} s)", spelling=Spelling.WHOLE
            ),
        ),
    ),
    Constant(
        label="how long a readiness probe may take",
        why=(
            "the third term, and the one a queued status adds to an eviction because it probes "
            "inside the same per-model lock, so the same three places have to agree or the "
            "boot-time check that the brain's deadline clears the sum is checking a sum no "
            "deployment runs (ADR-0030)"
        ),
        sites=(Site(SUPERVISOR, "DEFAULT_PROBE_TIMEOUT_S"),),
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_MODELHOST_PROBE_TIMEOUT_S:-{value}}"),
            Mention(
                SWAP_RUNBOOK,
                "`CORTEX_MODELHOST_PROBE_TIMEOUT_S` ({value} s)",
                spelling=Spelling.WHOLE,
            ),
            Mention(
                MODEL_MANAGER_DOC, "`DEFAULT_PROBE_TIMEOUT_S` ({value} s)", spelling=Spelling.WHOLE
            ),
        ),
    ),
)
