"""Turn a `just replay` date into the value `git log --since` reads from that day's midnight."""

import argparse
import re
import sys
from typing import cast

BARE_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
MIDNIGHT = "00:00"


def since_value(when: str) -> str:
    """Return a bare `YYYY-MM-DD` at midnight, since git reads one at the current time of day."""
    if BARE_DATE.fullmatch(when):
        return f"{when} {MIDNIGHT}"
    return when


def main(argv: list[str] | None = None) -> int:
    """Print the `--since` value for one replay date and return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Print the value `git log --since` reads a replay date as, from midnight.",
    )
    parser.add_argument("when", help="a bare date, or a date with a time, which is kept")
    args = parser.parse_args(argv)
    print(since_value(cast("str", args.when)))
    return 0


if __name__ == "__main__":  # pragma: no cover -- CLI entry point; main() is unit-tested
    sys.exit(main())
