"""Repo gate: fail when the committed Rust stub stops saying what the proto says."""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

from protocomments import ProtoReadError, normalize, proto_comments, rust_docs

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
    """One proto comment the committed stub no longer carries."""

    line: int
    text: str


class Scan(NamedTuple):
    """One comparison: what it was over, then what it could not account for."""

    leading: int
    trailing: int
    docs: int
    misses: list[Miss]


def _read(root: Path, relative: Path) -> str:
    """Read one side of the comparison, refusing a file that is absent or is not text."""
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        msg = f"cannot read {relative.as_posix()}: {err}"
        raise StubCheckError(msg) from err


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
    said = {normalize(doc) for doc in docs}
    return Scan(
        leading=sum(1 for comment in comments if comment.leading),
        trailing=sum(1 for comment in comments if not comment.leading),
        docs=len(docs),
        misses=[
            Miss(line=comment.line, text=comment.text.strip())
            for comment in comments
            if normalize(comment.text) not in said
        ],
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
        print(f"{PROTO.as_posix()}:{miss.line}: the stub carries no comment saying {miss.text!r}")
    if scanned.misses:
        print(
            f"\nstubcheck: {len(scanned.misses)} proto comment(s) are missing from "
            f"{STUB.as_posix()}. Regenerate the committed stubs with `just proto` and commit "
            f"them; a stub nobody regenerated goes on stating what the proto used to say.",
            file=sys.stderr,
        )
        return 1
    print(
        f"stubcheck OK: {scanned.leading + scanned.trailing} proto comment(s) under {given} "
        f"({scanned.leading} leading, {scanned.trailing} trailing) appear in the committed Rust "
        f"stub, over {scanned.docs} doc line(s) read"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
