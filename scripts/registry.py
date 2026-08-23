"""The registry `crosscheck.py` checks: every coupling this repo has written down, as one tuple.

The scan is all of the logic and the `*couplings.py` files beside this one are all of the data,
written in the vocabulary `couplings.py` holds. This module is the only place that names them,
which is its whole job: the 300-line cap has split the registry five times now, and each split
used to edit the scan itself to add an import and a name. It does not any more. A new part is a
new data file plus one line here, and `crosscheck.py` never learns that the registry has parts.
The sixth part arrived as a subject rather than as a split, which was the first time that claim
was paid rather than argued, and the seventh arrived the same way, which is the second. The eighth
went back to being a split, and paid the claim a third time from the other direction: the cap moved
five entries into a file of their own and nothing outside this line changed. So did the ninth,
which took the two endpoint entries out on the day a third joined them.

The order is the order faults are reported in, and nothing depends on it beyond that: the scan
never asks which file an entry came from, so a coupling moves house without the gate noticing.
Each part is named for the subject it holds rather than for when it was written, which is what
keeps a move an editorial decision instead of an archaeological one:

- `seamcouplings` ties one tree's code to another's, where neither toolchain can import the other.
- `endpointcouplings` ties each side's own endpoint, the address it answers on and its port, to
  compose, to the image, to the suites that dial it and to every document that states it.
- `shippedcouplings` ties the brain container's own defaults to the stacks and documents that
  restate them.
- `capturecouplings` ties one capture's own numbers, the edge and byte budget it rides with and
  the deadlines it runs under, to everything that ships or states them.
- `subagentcouplings` ties the subagent tier's admission budgets to the container limits that are
  their hard twins.
- `modelhostcouplings` ties the model-host sidecar's tier settings to the override that ships them.
- `emailcouplings` ties the email sidecar's shipped answers to the override that spells them again.
- `fixturecouplings` ties a stack built to be measured against to the suite that measures it, the
  only part whose subject the repo does not ship.
- `overlaycouplings` ties the overlay's TypeScript to the stylesheet that spends what it declares.

Counting the registry lives here too, beside the tuple the parts are joined into, because the size
of a collection is a fact about the collection rather than about any scan over it. `shape` is what
`crosscheck.py` prints on success and what every mutation table in this repo opens by stating.
"""

from typing import NamedTuple

from capturecouplings import CAPTURE_COUPLINGS
from couplings import Constant
from emailcouplings import EMAIL_COUPLINGS
from endpointcouplings import ENDPOINT_COUPLINGS
from fixturecouplings import FIXTURE_COUPLINGS
from modelhostcouplings import MODELHOST_COUPLINGS
from overlaycouplings import OVERLAY_COUPLINGS
from seamcouplings import SEAM_COUPLINGS
from shippedcouplings import SHIPPED_COUPLINGS
from subagentcouplings import SUBAGENT_COUPLINGS

CONSTANTS: tuple[Constant, ...] = (
    *SEAM_COUPLINGS,
    *ENDPOINT_COUPLINGS,
    *SHIPPED_COUPLINGS,
    *CAPTURE_COUPLINGS,
    *SUBAGENT_COUPLINGS,
    *MODELHOST_COUPLINGS,
    *EMAIL_COUPLINGS,
    *FIXTURE_COUPLINGS,
    *OVERLAY_COUPLINGS,
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
