"""The environment every git call in these checks runs with, read from one place."""

import os

GIT_PREFIX = "GIT_"


def git_env() -> dict[str, str]:
    """Return the ambient environment with every variable git exports to a hook removed."""
    return {key: value for key, value in os.environ.items() if not key.startswith(GIT_PREFIX)}
