"""Which drafter a hosted tier starts with: the one its setting names, or its file's own."""

_CORTEX_PICK = "unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
_SUBAGENT_PICK = "unsloth/gemma-4-E4B-it-qat-GGUF/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"

# The drafter the models mount holds beside a lineup file. Every entry is a file whose card names
# no slot limit for multi-token prediction; the subagent pick was measured drafting on two slots.
DRAFTERS = {
    _CORTEX_PICK: "unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf",
    _SUBAGENT_PICK: "unsloth/gemma-4-E4B-it-qat-GGUF/mtp-gemma-4-E4B-it-Q8_0.gguf",
}


def drafter_file(named: str | None, model_file: str) -> str:
    """The drafter a setting names, or the one the mount holds beside ``model_file`` when unset."""
    return DRAFTERS.get(model_file, "") if named is None else named


def drafts(model_file: str, parallel: int) -> bool:
    """Whether a server of ``parallel`` slots may draft: a file with no entry does on one only."""
    return parallel == 1 or model_file in DRAFTERS
