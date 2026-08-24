"""Which directory components no walk in this tree enters, in the one place all of them read."""

# Vendored trees, build output, tool caches, and the object database. Ten names, of which eight
# also appear in a `.gitignore`; the two that do not are argued above.
SKIPPED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".claude",
        "target",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "coverage",
    }
)
