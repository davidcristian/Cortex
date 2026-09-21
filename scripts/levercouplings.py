"""The coupling around the per-request trace setting: the wire name the brain sends llama.cpp."""

from couplings import Constant, Mention, Site

REQUEST = "brain/packages/inference/src/cortex_inference/request.py"
LEVER = "brain/packages/inference/src/cortex_inference/lever.py"
BACKEND = "brain/packages/inference/src/cortex_inference/backend.py"
INFERENCE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
GPU_RUNBOOK = "docs/runbooks/llamacpp-gpu.md"
SUBAGENTS_RUNBOOK = "docs/runbooks/subagents-cpu.md"
INFERENCE_DOC = "docs/modules/brain-inference.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator-config.md"

LEVER_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the per-request trace budget's wire name",
        why=(
            "the brain renders `GenerationBounds.trace_tokens` under this key and probes an "
            "endpoint with it at boot, and the GPU runbook prints the `curl` an operator asks "
            "that same question with, so a key the request stopped sending would leave that "
            "command, two module contracts and two runbook paragraphs describing a request this "
            "repo does not send (ADR-0049)"
        ),
        sites=(Site(REQUEST, "TRACE_BUDGET_KEY"),),
        mentions=(
            Mention(GPU_RUNBOOK, '"{value}":-2}'),
            Mention(GPU_RUNBOOK, "`{value}: 0` where this deployment's engine reads one"),
            Mention(GPU_RUNBOOK, "`{value}`, falling back to the tier's flag"),
            Mention(INFERENCE_DOC, "`{value}`, a sampler the engine reads from the request body"),
            Mention(ORCHESTRATOR_DOC, "as llama.cpp's `{value}`:"),
            Mention(SUBAGENTS_RUNBOOK, "per-request `{value}: 0` on top of the flags"),
            Mention(REQUEST, "engine parses ``{value}``,"),
            Mention(LEVER, "as llama.cpp's ``{value}``,"),
            Mention(LEVER, "A build that parses ``{value}``"),
            Mention(BACKEND, "does not parse ``{value}`` drops"),
            Mention(INFERENCE_CONFIG, "as llama.cpp's ``{value}``."),
        ),
    ),
)
