"""Repo gate: fail when the committed Rust stub stops saying what the proto says."""

import argparse
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

from protocomments import (
    COPIES,
    RULE,
    Comment,
    ProtoReadError,
    normalize,
    proto_comments,
    rust_docs,
)

# The two files this gate ties together, relative to the repo root: the source of truth for the
# seam, and the generated half that copies its prose verbatim.
PROTO = Path("proto/body.proto")
STUB = Path("body/crates/rpc/src/_generated/cortex.seam.v1.rs")

# The floor under the reading in the success line, and the same floor `dashcheck.py` carries: a
# side that came back empty has read nothing, and a comparison over nothing cannot fail.
MIN_COMMENTS = 1
MIN_DOCS = 1


class StubCheckError(Exception):
    """An input could not be read, or one side of the comparison came back empty."""


class Miss(NamedTuple):
    """One proto comment the committed stub carries fewer copies of than it is owed."""

    line: int
    text: str
    wanted: int
    found: int


class Scan(NamedTuple):
    """One comparison: what it was over, then what it could not account for."""

    leading: int
    trailing: int
    doubled: int
    docs: int
    misses: list[Miss]


def _read(root: Path, relative: Path) -> str:
    """Read one side of the comparison, refusing a file that is absent or is not text."""
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {relative.as_posix()}: {err}"
        raise StubCheckError(msg) from err


def owed(comments: Iterable[Comment]) -> Counter[str]:
    """How many copies of each normalized text the stub owes, a service comment owing two."""
    tally: Counter[str] = Counter()
    for comment in comments:
        text = normalize(comment.text)
        if text == RULE:
            tally[text] = MIN_DOCS
            continue
        tally[text] += COPIES if comment.service else 1
    return tally


def shortfalls(comments: Iterable[Comment], said: Counter[str]) -> list[Miss]:
    """Every text the stub holds fewer copies of than it owes, reported at its first proto line."""
    wanted = owed(comments)
    seen: set[str] = set()
    misses: list[Miss] = []
    for comment in comments:
        text = normalize(comment.text)
        if text in seen or said[text] >= wanted[text]:
            continue
        seen.add(text)
        misses.append(
            Miss(
                line=comment.line,
                text=comment.text.strip(),
                wanted=wanted[text],
                found=said[text],
            )
        )
    return misses


def check(root: Path) -> Scan:
    """Compare every comment in the proto body against the committed stub's doc comments."""
    proto_text = _read(root, PROTO)
    stub_text = _read(root, STUB)
    try:
        comments = proto_comments(proto_text)
    except ProtoReadError as err:
        msg = f"{PROTO.as_posix()}: {err}"
        raise StubCheckError(msg) from err
    docs = rust_docs(stub_text)
    if len(comments) < MIN_COMMENTS:
        msg = f"no comment in {PROTO.as_posix()}; a comparison over nothing cannot fail"
        raise StubCheckError(msg)
    if len(docs) < MIN_DOCS:
        msg = f"no doc comment in {STUB.as_posix()}; a comparison over nothing cannot fail"
        raise StubCheckError(msg)
    return Scan(
        leading=sum(1 for comment in comments if comment.leading),
        trailing=sum(1 for comment in comments if not comment.leading),
        doubled=sum(1 for comment in comments if comment.service),
        docs=len(docs),
        misses=shortfalls(comments, Counter(normalize(doc) for doc in docs)),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the gate; print any misses and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Fail when a proto comment is missing from the committed Rust stub.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repo root holding the proto and the committed stub (default: current directory)",
    )
    args = parser.parse_args(argv)
    given: Path = args.root
    if not given.is_dir():
        print(f"stubcheck: root {given} is not a directory", file=sys.stderr)
        return 2
    root = given.resolve()
    try:
        scanned = check(root)
    except StubCheckError as err:
        print(f"stubcheck: {err}", file=sys.stderr)
        return 2
    for miss in scanned.misses:
        print(
            f"{PROTO.as_posix()}:{miss.line}: the stub says {miss.text!r} {miss.found} time(s), "
            f"and this comment is owed {miss.wanted}"
        )
    if scanned.misses:
        print(
            f"\nstubcheck: {len(scanned.misses)} proto comment(s) are missing from "
            f"{STUB.as_posix()}, or stand there in fewer copies than it holds; a comment on a "
            "service is written into both the client and the server module. Regenerate the "
            "committed stubs with `just proto` and commit them; a stub nobody regenerated goes "
            "on stating what the proto used to say.",
            file=sys.stderr,
        )
        return 1
    print(
        f"stubcheck OK: {scanned.leading + scanned.trailing} proto comment(s) under {given} "
        f"({scanned.leading} leading, {scanned.trailing} trailing, {scanned.doubled} owed two "
        f"copies) appear in the committed Rust stub, over {scanned.docs} doc line(s) read"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
