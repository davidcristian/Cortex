"""The files each hosted model is started with, and the setting that names each."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from cortex_model_manager.spec import ModelSpec

_FLAG_SUFFIXES = (("--model", ""), ("--mmproj", "_MMPROJ"), ("--model-draft", "_DRAFT"))


@dataclass(frozen=True, slots=True)
class ModelFiles:
    """Checks that every file a model's command line names is there before the model loads."""

    tiers: Mapping[str, str]
    is_file: Callable[[str], bool]

    def missing(self, spec: ModelSpec) -> str | None:
        """A sentence naming the first absent file of ``spec`` and its setting, or ``None``."""
        tier = self.tiers[spec.model]
        for flag, suffix in _FLAG_SUFFIXES:
            if flag not in spec.argv:
                continue
            path = spec.argv[spec.argv.index(flag) + 1]
            if not self.is_file(path):
                return (
                    f"CORTEX_MODEL_FILE_{tier}{suffix} names {path!r}, which is not a file in "
                    "the model host's container, so the model was not loaded"
                )
        return None
