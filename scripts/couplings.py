"""The registry `crosscheck.py` reads: every value this repo spells in more than one place.

Split out of the scan, which is all of the logic; this file and `overlaycouplings.py` beside it
are all of the data, and they grow every time a coupling is found. This file holds the vocabulary
every entry is written in and the entries that tie the body to the brain; the entries that tie the
overlay's TypeScript to its own stylesheet went next door when the one file outgrew the 300-line
cap, and `crosscheck.py` walks the two halves as one registry. Each entry carries the reason its
places must agree, printed with any failure, because a gate that says only "these differ" leaves
the reader to rediscover why they must not.

**Two kinds of far side**, and the difference is what a rename has to walk past:

- A **site** DECLARES the value, so the scan reads it out and compares it. Both sides being
  declarations is the original case (`MAX_CAPTURE_BYTES` against `MAX_IMAGE_BYTES`).
- A **mention** SPENDS the value without declaring it: a metadata key spelled inside a shell
  string in a compose healthcheck, a custom property a stylesheet reads back with `var(...)`, a
  bare literal a component compares against. There is no declaration there to parse, so the scan
  renders the agreed value into the mention's template and requires the result to appear in the
  file. That is not circular: the template carries the SHAPE (`var({value},`) and the value comes
  from the declaring site, so a rename on either side leaves the rendered needle unfound. It is
  also why a bare literal does not have to be promoted to a named constant first.

A mention is a presence check by default: one bounded occurrence satisfies it however many the
file spends, so a half applied rename that updates one of two identical comparisons leaves the
gate green with the other one dead. `occurrences` closes that where a mention's several
occurrences are one set, pinning an EXACT count rather than a floor. It is opt in on purpose: a
floor cannot notice it has gone stale, and a count over a far side whose occurrences are
independent of each other is arithmetic that reddens on every unrelated addition. Set it only
where losing one occurrence is a defect rather than a design change.

**`Relation`** says how a constant's sites must stand to each other. Most couplings are
equalities. A few are orderings, where one side's bound has to sit under another's rather than
equal it, and an ordering compares numbers only. One is a membership, where the value one tree
produces has to be one of the several another tree accepts, which is neither an equality nor an
ordering: the collection is the whole point, and the last site is the one that declares it.
"""

from enum import Enum
from typing import NamedTuple

# What a mention's template substitutes. A template without it would tie nothing and is refused.
PLACEHOLDER = "{value}"


class Relation(Enum):
    """How the values at a constant's sites must stand to each other."""

    EQUAL = "identical"
    ORDERED = "non-decreasing in registry order"
    MEMBER = "members of the collection the last site declares"


class Site(NamedTuple):
    """One declaration: a repo-relative file and the identifier declared in it."""

    path: str
    name: str


class Mention(NamedTuple):
    """One place that spends a value without declaring it, and the shape it appears in.

    ``occurrences`` unset asks only that the rendered needle appear. Set, it asks that it appear
    exactly that many times, for a far side whose several occurrences must move together.
    """

    path: str
    template: str
    occurrences: int | None = None


class Constant(NamedTuple):
    """One value every site and mention must hold in common, and why they must."""

    label: str
    why: str
    sites: tuple[Site, ...]
    relation: Relation = Relation.EQUAL
    mentions: tuple[Mention, ...] = ()


BASE_COMPOSE = "docker/docker-compose.yml"

SEAM_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the screen-capture byte ceiling",
        why=(
            "the brain sends its own budget as the capture request's max_bytes and re-verifies "
            "it on receipt, so a body ceiling above the brain's would let a capture pass the "
            "body and be refused in the brain (ADR-0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_CAPTURE_BYTES"),
            Site("brain/packages/core/src/cortex_core/images.py", "MAX_IMAGE_BYTES"),
        ),
    ),
    Constant(
        label="the seam token's metadata key",
        why=(
            "each side attaches the token under this key and the other reads it back out, in "
            "both seam directions, so a disagreement fails every authenticated call (ADR-0016)"
        ),
        sites=(
            Site("body/crates/rpc/src/auth.rs", "SEAM_TOKEN_HEADER"),
            Site("body/crates/rpc/src/client.rs", "SEAM_TOKEN_HEADER"),
            Site("brain/packages/seam/src/cortex_seam/__init__.py", "SEAM_TOKEN_HEADER"),
        ),
        # The fourth copy, and the one whose drift would be silent: the brain container's own
        # healthcheck dials Health with the token attached, from a Python one-liner inside YAML.
        mentions=(Mention(BASE_COMPOSE, "'{value}'"),),
    ),
    Constant(
        label="the session-title truncation bound",
        why=(
            "the brain bounds every title it lists to this, and the overlay bounds the live "
            "title it derives for a chat the brain has not listed yet, so a disagreement shows "
            "one chat under two names at once: the header cut at one bound while its own "
            "switcher row carries the other (ADR-0021)"
        ),
        sites=(
            Site("brain/packages/core/src/cortex_core/sessions.py", "TITLE_MAX"),
            Site("body/app/src/overlay/sessionState.ts", "TITLE_MAX"),
        ),
    ),
    Constant(
        label="the capture edge ceiling under the brain's image bound",
        why=(
            "the body clamps every request to its own ceiling and the brain refuses any image "
            "past its bound, so a body ceiling above the brain's would spend a real capture on "
            "an image the brain then throws away (ADR-0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_EDGE_CEILING"),
            Site("brain/packages/core/src/cortex_core/images.py", "MAX_IMAGE_EDGE"),
        ),
        relation=Relation.ORDERED,
    ),
    Constant(
        label="the capture encoding inside the brain's allow-list",
        why=(
            "the body encodes every capture as this one type and the brain refuses any image "
            "whose type its allow-list does not carry, so an encoding the list lost would spend "
            "a real capture on an image the brain then throws away (ADR-0029)"
        ),
        # The value first and the collection last, which is the order this relation reads: the
        # body produces one encoding, the brain accepts a set of them, and the tie is that the
        # one is among the several. Neither an equality (the sets differ) nor an ordering.
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "CAPTURE_MIME"),
            Site("brain/packages/core/src/cortex_core/images.py", "ALLOWED_MIME_TYPES"),
        ),
        relation=Relation.MEMBER,
    ),
    Constant(
        label="the body-client receive limit above the capture ceiling",
        why=(
            "a capture rides back to the brain as one gRPC message, so a receive limit at or "
            "below the byte ceiling would refuse in the transport a capture both policies "
            "allowed, and the refusal would read as a body fault (ADR-0023/0029)"
        ),
        sites=(
            Site("body/crates/core/src/os/screen_policy.rs", "MAX_CAPTURE_BYTES"),
            Site(
                "brain/packages/body_client/src/cortex_body_client/gateway.py", "MAX_RECEIVE_BYTES"
            ),
        ),
        relation=Relation.ORDERED,
    ),
    Constant(
        label="the capture-screen tool's name",
        why=(
            "the brain names the tool and the overlay lights its capture dot by matching that "
            "name off the wire, so a rename leaves the dot dark on every capture (ADR-0029)"
        ),
        sites=(
            Site("brain/packages/core/src/cortex_core/screen_tool.py", "CAPTURE_SCREEN_TOOL_NAME"),
            Site("body/app/src/overlay/turnState.ts", "CAPTURE_SCREEN_TOOL"),
        ),
    ),
    Constant(
        label="the reasoning trace's status state",
        why=(
            "the brain sends deliberation under this state and the overlay accumulates the "
            "trace and styles its chip by comparing against the bare literal, so a rename "
            "leaves the reasoning unaccumulated and the chip unstyled (ADR-0020)"
        ),
        sites=(Site("brain/packages/core/src/cortex_core/output_channels.py", "THINKING_STATE"),),
        # The component's two comparisons are one set: the same chip's class and its accessible
        # name, both deciding on this one state. A rename applied to one of them leaves the other
        # dead with the file still spelling the new value, which is what the count refuses.
        mentions=(
            Mention("body/app/src/overlay/turnState.ts", 'event.state === "{value}"'),
            Mention(
                "body/app/src/components/Message.tsx",
                'message.statusState === "{value}"',
                occurrences=2,
            ),
        ),
    ),
    Constant(
        label="the brain's seam port",
        why=(
            "the compose stack publishes this port and dials it in its own healthcheck, and the "
            "host body's default endpoints name it too, so a change to the server default alone "
            "leaves every one of them pointed at a port nothing listens on (ADR-0003/0016)"
        ),
        sites=(
            Site(
                "brain/packages/orchestrator/src/cortex_orchestrator/config.py", "DEFAULT_SEAM_PORT"
            ),
        ),
        # The publish is `host:container` and it is the container half that this value names, so
        # its template spells both: `127.0.0.1:{value}` alone was satisfied by the host half and
        # left the half that has to match the server's own default free to drift.
        mentions=(
            Mention(BASE_COMPOSE, '"127.0.0.1:{value}:{value}"'),
            Mention(BASE_COMPOSE, "insecure_channel('127.0.0.1:{value}')"),
            Mention("body/app/src-tauri/src/seam.rs", '"http://127.0.0.1:{value}"'),
            Mention("body/app/src-tauri/src/converse.rs", '"http://127.0.0.1:{value}"'),
        ),
    ),
)
