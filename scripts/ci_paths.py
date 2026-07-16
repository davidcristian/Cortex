"""CI path classifier: decide which toolchain jobs must run for a set of changed files.

Reads newline-separated repo-relative paths (the output of ``git diff --name-only``)
from stdin and writes exactly three ``GITHUB_OUTPUT``-format lines to stdout:
``python=true|false``, ``rust=true|false``, then ``overlay=true|false``. Each path is
classified by ordered rules (first match wins); the result is the union over all paths.
Unmatched paths fail closed to ALL toolchains -- unknown means over-test, never
under-test (ADR-0006). The script must keep running under a plain ``python3`` on a
GitHub runner: stdlib only, no uv sync.
"""

import sys
from typing import Literal, NamedTuple


class Verdict(NamedTuple):
    """Which toolchain gates a changed path affects, plus a label for CI logs."""

    label: str
    python: bool
    rust: bool
    overlay: bool


ALL = Verdict("all", python=True, rust=True, overlay=True)
PYTHON_ONLY = Verdict("python", python=True, rust=False, overlay=False)
RUST_ONLY = Verdict("rust", python=False, rust=True, overlay=False)
OVERLAY_ONLY = Verdict("overlay", python=False, rust=False, overlay=True)
NEITHER = Verdict("neither", python=False, rust=False, overlay=False)
# Same effect as ALL, but the distinct label makes CI logs say WHY every job ran.
DEFAULT = Verdict("all (fail-closed default)", python=True, rust=True, overlay=True)


class Rule(NamedTuple):
    """One ordered classification rule: how a path matches and what it affects."""

    kind: Literal["exact", "prefix", "suffix"]
    pattern: str
    verdict: Verdict


# Ordered, first match wins; this list is normative in ADR-0006 -- change them together.
# `body/app/` (the React overlay) is the OVERLAY tree, gating the node toolchain. Its
# host-native Tauri shell lives beside it at `body/app/src-tauri/` but is Rust, not node:
# `check-body` fmt-checks it (ADR-0011), so that subtree is carved back to RUST by a rule
# ordered BEFORE `body/app/`. Both `body/app/*` rules sit BEFORE the broader `body/` -> RUST
# rule (first match wins). The `.md` suffix rule sits last on purpose: files inside a
# toolchain tree are never assumed inert (tests may read them as fixtures), so e.g.
# brain/README.md is PYTHON.
RULES: tuple[Rule, ...] = (
    Rule("exact", "justfile", ALL),
    Rule("exact", ".python-version", ALL),
    Rule("prefix", "proto/", ALL),
    Rule("prefix", "scripts/", ALL),
    Rule("prefix", ".github/workflows/", ALL),
    Rule("exact", "ruff.toml", PYTHON_ONLY),
    Rule("prefix", "brain/", PYTHON_ONLY),
    Rule("prefix", "body/app/src-tauri/", RUST_ONLY),
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


def classify(path: str) -> Verdict:
    """Classify one repo-relative path; unmatched paths fail closed to all toolchains."""
    for rule in RULES:
        if matches(rule, path):
            return rule.verdict
    return DEFAULT


def main(lines: list[str] | None = None) -> int:
    """Classify every stdin path; print the union as exactly three GITHUB_OUTPUT lines."""
    python = False
    rust = False
    overlay = False
    source = sys.stdin if lines is None else lines
    for raw in source:
        path = raw.strip()
        if not path:
            continue
        verdict = classify(path)
        print(f"ci-paths: {path} -> {verdict.label}", file=sys.stderr)
        python |= verdict.python
        rust |= verdict.rust
        overlay |= verdict.overlay
    print(f"python={'true' if python else 'false'}")
    print(f"rust={'true' if rust else 'false'}")
    print(f"overlay={'true' if overlay else 'false'}")
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
