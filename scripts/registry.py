"""Every constant `crosscheck.py` compares, joined from the `*couplings.py` files beside it.

`crosscheck.py` has the logic and those files have the data, written with the types `couplings.py`
defines. This module is the only place that names them, so a new part is a new data file plus one
line in the list below and one in `CONSTANTS`. A part is a `<subject>couplings.py` module with a
`<SUBJECT>_COUPLINGS` tuple in it, every entry belongs to exactly one part, and the order below is
the order faults are reported in.

- `wirecouplings` ties one tree's code to another's, where neither toolchain can import the other.
- `endpointcouplings` ties each side's endpoint, the address it listens on and its port, to
  compose, to the image, to the tests that dial it and to every document that states it.
- `shippedcouplings` ties the brain container's defaults to the stacks and documents that restate
  them.
- `capturecouplings` ties one capture's numbers, the image size and byte budget sent with it and
  the deadlines it runs under, to everything that ships or states them.
- `boundscouplings` ties the four bounds of one delegated run, none of which any stack ships, to
  the runbook and the module contract that quote each.
- `subagentcouplings` ties the subagent tier's admission budgets to the container limits that must
  match them.
- `modelhostcouplings` ties the model-host sidecar's tier settings to the override that ships them.
- `tracecouplings` ties the wire name the brain sends a per-request trace budget under to the
  command an operator asks the same question with, and to every document and comment that writes
  the name again.
- `imagecouplings` ties the two llama.cpp images this repo starts servers from to the test setups
  that name one, which is the pair the check over the recorded image rows does not reach.
- `emailcouplings` ties the email sidecar's shipped answers to the override that writes them again,
  and what the sidecar writes for the brain, its four own texts, the key it declares a sender
  under, the kind word in that declaration and the two field names it is written under, to the
  brain package that restates or reads it.
- `fixturecouplings` ties a stack built to be measured to the tests that measure it, the only part
  whose subject the repo does not ship.
- `overlaycouplings` ties the overlay's TypeScript to the stylesheet that uses what it declares.
- `logcouplings` ties the brain's log field names, the one name each work identity is written
  under, to every line that writes it and every runbook that tells an operator to grep it.
- `trailcouplings` ties the words one line of either per-item log is found by, which are the recall
  log's logger, the message it opens with, the field it is measured on, and the tool audit's own
  logger and message, to the code that writes them, the reader outside the brain that measures
  them, the documents that state them, and the test that asserts the rendered line. Its last entry
  is of another kind: the identifier a self-named sink declares its logger under, which is how the
  check over those lines finds its set of sinks.

`shape` counts places and not parts, so the list above is the whole answer to what the registry is
written in, in the one place a reader also learns what each part is for.
"""

from typing import NamedTuple

from boundscouplings import BOUNDS_COUPLINGS
from capturecouplings import CAPTURE_COUPLINGS
from couplings import Constant
from emailcouplings import EMAIL_COUPLINGS
from endpointcouplings import ENDPOINT_COUPLINGS
from fixturecouplings import FIXTURE_COUPLINGS
from imagecouplings import IMAGE_COUPLINGS
from logcouplings import LOG_COUPLINGS
from modelhostcouplings import MODELHOST_COUPLINGS
from overlaycouplings import OVERLAY_COUPLINGS
from shippedcouplings import SHIPPED_COUPLINGS
from subagentcouplings import SUBAGENT_COUPLINGS
from tracecouplings import TRACE_COUPLINGS
from trailcouplings import TRAIL_COUPLINGS
from wirecouplings import WIRE_COUPLINGS

CONSTANTS: tuple[Constant, ...] = (
    *WIRE_COUPLINGS,
    *ENDPOINT_COUPLINGS,
    *SHIPPED_COUPLINGS,
    *CAPTURE_COUPLINGS,
    *BOUNDS_COUPLINGS,
    *SUBAGENT_COUPLINGS,
    *MODELHOST_COUPLINGS,
    *TRACE_COUPLINGS,
    *IMAGE_COUPLINGS,
    *EMAIL_COUPLINGS,
    *FIXTURE_COUPLINGS,
    *OVERLAY_COUPLINGS,
    *LOG_COUPLINGS,
    *TRAIL_COUPLINGS,
)


class Shape(NamedTuple):
    """How big a registry is: its entries, and the places that declare, use and count a value."""

    entries: int
    sites: int
    mentions: int
    counted: int


def shape(constants: tuple[Constant, ...]) -> Shape:
    """Count one registry's entries and the places that declare, use and count a value."""
    mentions = [mention for constant in constants for mention in constant.mentions]
    return Shape(
        entries=len(constants),
        sites=sum(len(constant.sites) for constant in constants),
        mentions=len(mentions),
        counted=sum(1 for mention in mentions if mention.occurrences is not None),
    )
