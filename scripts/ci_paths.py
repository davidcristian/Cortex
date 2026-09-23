"""CI path classifier: decide which toolchain jobs must run for a set of changed files."""

import sys
from typing import Literal, NamedTuple


class Jobs(NamedTuple):
    """Which toolchain jobs a changed path affects, plus a label for CI logs."""

    label: str
    python: bool
    rust: bool
    overlay: bool
    shell: bool


# `shell=` here is this NamedTuple's fourth field, not subprocess's, which is what S604 is
# about: nothing in this module runs a process. Ruff matches that rule on the keyword alone.
ALL = Jobs("all", python=True, rust=True, overlay=True, shell=True)  # noqa: S604
PYTHON_ONLY = Jobs("python", python=True, rust=False, overlay=False, shell=False)
RUST_ONLY = Jobs("rust", python=False, rust=True, overlay=False, shell=False)
OVERLAY_ONLY = Jobs("overlay", python=False, rust=False, overlay=True, shell=False)
SHELL = Jobs("rust+shell", python=False, rust=True, overlay=False, shell=True)  # noqa: S604
NEITHER = Jobs("neither", python=False, rust=False, overlay=False, shell=False)
DEFAULT = Jobs(  # noqa: S604
    "all (fail-closed default)",
    python=True,
    rust=True,
    overlay=True,
    shell=True,
)


class Rule(NamedTuple):
    """One ordered classification rule: how a path matches and what it affects."""

    kind: Literal["exact", "prefix", "suffix"]
    pattern: str
    jobs: Jobs


# Ordered, first match wins. The two `body/app/` rules come before the broader `body/` rule, and
# the `.md` suffix rule comes last, so a markdown file inside a toolchain tree stays that
# toolchain's.
RULES: tuple[Rule, ...] = (
    Rule("exact", "justfile", ALL),
    Rule("exact", ".python-version", ALL),
    Rule("prefix", "proto/", ALL),
    Rule("prefix", "scripts/", ALL),
    Rule("prefix", ".github/workflows/", ALL),
    Rule("exact", "ruff.toml", PYTHON_ONLY),
    Rule("prefix", "brain/", PYTHON_ONLY),
    Rule("prefix", "body/app/src-tauri/", SHELL),
    Rule("prefix", "body/app/", OVERLAY_ONLY),
    Rule("prefix", "body/", RUST_ONLY),
    Rule("prefix", "docs/", NEITHER),
    Rule("prefix", ".claude/", NEITHER),
    Rule("exact", ".gitignore", NEITHER),
    Rule("exact", ".pre-commit-config.yaml", NEITHER),
    Rule("exact", "LICENSE", NEITHER),
    Rule("exact", ".github/dependabot.yml", NEITHER),
    Rule("suffix", ".md", NEITHER),
)


def matches(rule: Rule, path: str) -> bool:
    """Return True when ``path`` matches the rule's pattern."""
    if rule.kind == "exact":
        return path == rule.pattern
    if rule.kind == "prefix":
        return path.startswith(rule.pattern)
    return path.endswith(rule.pattern)


def classify(path: str) -> Jobs:
    """Classify one repo-relative path; unmatched paths fail closed to all toolchains."""
    for rule in RULES:
        if matches(rule, path):
            return rule.jobs
    return DEFAULT


def main(lines: list[str] | None = None) -> int:
    """Classify every stdin path; print the union as exactly four GITHUB_OUTPUT lines."""
    python = False
    rust = False
    overlay = False
    shell = False
    source = sys.stdin if lines is None else lines
    for raw in source:
        path = raw.strip()
        if not path:
            continue
        jobs = classify(path)
        print(f"ci-paths: {path} -> {jobs.label}", file=sys.stderr)
        python |= jobs.python
        rust |= jobs.rust
        overlay |= jobs.overlay
        shell |= jobs.shell
    print(f"python={'true' if python else 'false'}")
    print(f"rust={'true' if rust else 'false'}")
    print(f"overlay={'true' if overlay else 'false'}")
    print(f"shell={'true' if shell else 'false'}")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
