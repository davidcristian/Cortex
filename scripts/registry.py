"""The registry `crosscheck.py` checks: every coupling this repo has written down, as one tuple.

The scan holds all of the logic and the `*couplings.py` files beside this one hold all of the data,
written in the vocabulary `couplings.py` defines. This module is the only place that names them, so
a part arrives as a new data file plus one line below rather than as an edit to the scan. A part
arrives two ways: as a split when the 300-line cap outgrows a file, and as a subject when a
coupling belongs under none of the ones already here.

A part is a `<subject>couplings.py` holding a `<SUBJECT>_COUPLINGS` tuple, which is the convention
the suite finds one on disk by, and every entry lives in exactly one part: `CONSTANTS` is the parts
joined and holds nothing of its own, so a coupling written inline here would gate normally and sit
under none of the names below. Both halves are asserted rather than assumed, an export under
another name and an entry outside every part each failing with a sentence.

The order is the order faults are reported in, and nothing else depends on it: the scan never asks
which file an entry came from, so a coupling can move between parts with every gate still green.
Each part is named for the subject it holds rather than for when it was written. This list is the
whole answer to what the registry is written in, so counting it counts the parts, and
`test_registry_names_every_part_in_the_order_it_reads_them` holds it to the directory beside it and
to the order the tuple reads them in:

- `seamcouplings` ties one tree's code to another's, where neither toolchain can import the other.
- `endpointcouplings` ties each side's own endpoint, the address it answers on and its port, to
  compose, to the image, to the suites that dial it and to every document that states it.
- `shippedcouplings` ties the brain container's own defaults to the stacks and documents that
  restate them.
- `capturecouplings` ties one capture's own numbers, the edge and byte budget it rides with and
  the deadlines it runs under, to everything that ships or states them.
- `boundscouplings` ties the four bounds one delegated run stands between, none of which any stack
  ships, to the runbook and the module contract that quote each.
- `subagentcouplings` ties the subagent tier's admission budgets to the container limits that are
  their hard twins.
- `modelhostcouplings` ties the model-host sidecar's tier settings to the override that ships them.
- `emailcouplings` ties the email sidecar's shipped answers to the override that spells them again,
  and what the sidecar writes for the brain, its four own texts, the key it declares a sender
  under and the kind word that declaration carries, to the brain package that restates or reads
  it.
- `fixturecouplings` ties a stack built to be measured against to the suite that measures it, the
  only part whose subject the repo does not ship.
- `overlaycouplings` ties the overlay's TypeScript to the stylesheet that spends what it declares.
- `logcouplings` ties the brain's log vocabulary, the one name each work identity is written
  under, to every line that spells it and every runbook that tells an operator to grep it.
- `trailcouplings` ties the words one line of either per-line trail is found by, which are the
  recall trail's logger, the message it opens with, the field it is measured on, and the tool
  audit's own logger and message, to the sinks that write them, the reader outside the brain that
  measures them, the documents that state them, the call the tool audit hands its message to by
  name, and the assertion its suite makes on the rendered line. Its last entry is of another
  kind: the identifier a self-named sink declares its logger under, which is how the guard
  holding those lines to their calls reads its set of sinks.

Counting the registry lives here too, beside the tuple the parts are joined into, because the size
of a collection is a fact about the collection rather than about any scan over it. `shape` is what
`crosscheck.py` prints on success and what every mutation table in this repo opens by stating.

It counts places and not parts. Nothing the scan does depends on how many files the data sits in;
a part that never reached the tuple is caught by the suite reading this directory rather than by
any number; and a whole part gone missing already moves the entry count. So the part count is
answered by the list above, in the one place a reader also learns what each part is for.
"""

from typing import NamedTuple

from boundscouplings import BOUNDS_COUPLINGS
from capturecouplings import CAPTURE_COUPLINGS
from couplings import Constant
from emailcouplings import EMAIL_COUPLINGS
from endpointcouplings import ENDPOINT_COUPLINGS
from fixturecouplings import FIXTURE_COUPLINGS
from logcouplings import LOG_COUPLINGS
from modelhostcouplings import MODELHOST_COUPLINGS
from overlaycouplings import OVERLAY_COUPLINGS
from seamcouplings import SEAM_COUPLINGS
from shippedcouplings import SHIPPED_COUPLINGS
from subagentcouplings import SUBAGENT_COUPLINGS
from trailcouplings import TRAIL_COUPLINGS

CONSTANTS: tuple[Constant, ...] = (
    *SEAM_COUPLINGS,
    *ENDPOINT_COUPLINGS,
    *SHIPPED_COUPLINGS,
    *CAPTURE_COUPLINGS,
    *BOUNDS_COUPLINGS,
    *SUBAGENT_COUPLINGS,
    *MODELHOST_COUPLINGS,
    *EMAIL_COUPLINGS,
    *FIXTURE_COUPLINGS,
    *OVERLAY_COUPLINGS,
    *LOG_COUPLINGS,
    *TRAIL_COUPLINGS,
)


class Shape(NamedTuple):
    """How big a registry is: the collection any reading over it is a reading over.

    Four numbers, because a mutation table that says "one of N" without saying what N counts has
    not named its collection: how many entries, how many places declare a value, how many spend
    one, and how many of those spends pin an exact count rather than a presence.
    """

    entries: int
    sites: int
    mentions: int
    counted: int


def shape(constants: tuple[Constant, ...]) -> Shape:
    """Count one registry's entries and the places they declare, spend and pin a value in."""
    mentions = [mention for constant in constants for mention in constant.mentions]
    return Shape(
        entries=len(constants),
        sites=sum(len(constant.sites) for constant in constants),
        mentions=len(mentions),
        counted=sum(1 for mention in mentions if mention.occurrences is not None),
    )
