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

One entry reaches past that override and into the body's, because the token budget is half of a
measured pair whose other half the brain sets: each file's prose names the other file's number,
and a comment that states what the deployment does is a far side like any other sentence that
becomes wrong when the value moves (ADR-0029's comment addendum).
"""

from couplings import Constant, Mention, Site, Spelling

BODY_COMPOSE = "docker/docker-compose.body.yml"
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
VISION_RUNBOOK = "docs/runbooks/vision.md"
CAPTURE_CHECK = "docs/host/tasks/012-display-capture-path.md"

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
        # The runbook's row spells this number twice and only the legend was held, which is the
        # worse half of that pair to hold: `99` = all says what the value MEANS to llama.cpp and
        # stays true after the default moves, where the Default cell states what ships and does
        # not. Both are registered rather than one swapped for the other, the legend being the
        # sentinel this default was chosen to be; cell walls pin the second without pinning a word.
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_NGL:-{value}}"),
            Mention(GPU_COMPOSE, "${CORTEX_NGL_BRAIN:-{value}}"),
            Mention(GPU_RUNBOOK, "`{value}` = all"),
            Mention(GPU_RUNBOOK, "| `{value}` |"),
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
            "edge is the other half of, and the override, both runbooks, the module contract "
            "and the config's own comment each state it as the shipped budget, so a budget "
            "retuned in the field alone would pay the edge's pixels for an encoder still "
            "refusing to spend tokens on them (ADR-0029 legibility addendum)"
        ),
        sites=(Site(MODELHOST_CONFIG, "DEFAULT_IMAGE_MAX_TOKENS"),),
        # Sorted by the survey's tense test: a sentence that becomes WRONG when the budget moves
        # is a far side, and one that becomes HISTORY is not. The body override's comment argues
        # for a 2048 px capture by naming this budget, and the config's and the GPU override's
        # own comments name their own; each states what the deployment does, so each is held.
        # The GPU runbook holds three: its env table's claim, that row's own Example cell, which
        # is a second spelling of the same answer on the same line and pinned by the cell walls
        # rather than by any of the sentence between them, and the recipe block a reader copies,
        # pinned at a line start so the measured table's `=1024` arm below it stays out. That arm,
        # the picture's token cost in the vision runbook and the reservation tables
        # in the swap runbook are history: each was measured AT this budget and goes on being
        # true after it moves. The vision runbook's three are counted rather than merely present,
        # because all three call this number the shipped one and a file left naming two different
        # shipped budgets is a defect rather than a design change. The last mention is a host
        # check, which is a live instruction and not a record: a completed check's file shrinks to
        # a heading, its status and a pointer, so the sentence naming this budget exists only
        # while somebody may still read it and act on it.
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_IMAGE_MAX_TOKENS:-{value}}"),
            Mention(GPU_COMPOSE, "{value} is the default"),
            Mention(GPU_RUNBOOK, "`{value}` is the default, paired with"),
            Mention(GPU_RUNBOOK, "| `{value}` |"),
            Mention(GPU_RUNBOOK, "\nCORTEX_IMAGE_MAX_TOKENS={value}"),
            Mention(BODY_COMPOSE, "CORTEX_IMAGE_MAX_TOKENS={value}"),
            Mention(MODELHOST_CONFIG, "{value} is the default because"),
            Mention(VISION_RUNBOOK, "CORTEX_IMAGE_MAX_TOKENS={value}", occurrences=3),
            Mention(MODEL_MANAGER_DOC, "`{value}` by default"),
            Mention(CAPTURE_CHECK, "CORTEX_IMAGE_MAX_TOKENS={value}"),
        ),
    ),
    # The sentinel both reasoning budgets default to, declared once under the underscore that says
    # no module imports it and read here anyway: a `Site` names what a file declares, not what a
    # module exports, and this scan reads text rather than importing anything (see `couplings.py`).
    Constant(
        label="the unbounded reasoning budget both tiers ship with",
        why=(
            "llama.cpp's own word for a trace nobody bounds is the default for the cortex and "
            "for the deep tier, and the override spells it again for each while the runbook and "
            "the module contract state it as the answer that emits no flag, so a deployment "
            "given a budget in the config alone would still start both tiers unbounded "
            "(ADR-0030, and the thinking-budget measurements in the GPU runbook)"
        ),
        sites=(Site(MODELHOST_CONFIG, "_UNRESTRICTED_REASONING"),),
        # The runbook gives the two tiers a row each and both Default cells were free while the
        # sentence above them was held. They are counted at 2 because they are one set: the entry's
        # own reason is that this answer ships for BOTH tiers, so a file naming one of them
        # unbounded and the other bounded states a split this config does not have.
        mentions=(
            Mention(GPU_COMPOSE, "${CORTEX_REASONING_BUDGET:-{value}}"),
            Mention(GPU_COMPOSE, "${CORTEX_REASONING_BUDGET_BRAIN:-{value}}"),
            Mention(GPU_RUNBOOK, "`{value}` (the default) emits no flag"),
            Mention(GPU_RUNBOOK, "| `{value}` |", occurrences=2),
            Mention(MODEL_MANAGER_DOC, "`{value}`, the default, is the engine's own word"),
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
