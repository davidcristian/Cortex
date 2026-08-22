"""The registry `crosscheck.py` checks: every coupling this repo has written down, as one tuple.

The scan is all of the logic and the `*couplings.py` files beside this one are all of the data,
written in the vocabulary `couplings.py` holds. This module is the only place that names them,
which is its whole job: the 300-line cap has split the registry four times now, and each split
used to edit the scan itself to add an import and a name. It does not any more. A new part is a
new data file plus one line here, and `crosscheck.py` never learns that the registry has parts.
The sixth part arrived as a subject rather than as a split, which is the first time that claim
was paid rather than argued.

The order is the order faults are reported in, and nothing depends on it beyond that: the scan
never asks which file an entry came from, so a coupling moves house without the gate noticing.
Each part is named for the subject it holds rather than for when it was written, which is what
keeps a move an editorial decision instead of an archaeological one:

- `seamcouplings` ties one tree's code to another's, where neither toolchain can import the other.
- `shippedcouplings` ties the brain container's own defaults to the stacks and documents that
  restate them.
- `subagentcouplings` ties the subagent tier's admission budgets to the container limits that are
  their hard twins.
- `modelhostcouplings` ties the model-host sidecar's tier settings to the override that ships them.
- `emailcouplings` ties the email sidecar's shipped answers to the override that spells them again.
- `overlaycouplings` ties the overlay's TypeScript to the stylesheet that spends what it declares.
"""

from couplings import Constant
from emailcouplings import EMAIL_COUPLINGS
from modelhostcouplings import MODELHOST_COUPLINGS
from overlaycouplings import OVERLAY_COUPLINGS
from seamcouplings import SEAM_COUPLINGS
from shippedcouplings import SHIPPED_COUPLINGS
from subagentcouplings import SUBAGENT_COUPLINGS

CONSTANTS: tuple[Constant, ...] = (
    *SEAM_COUPLINGS,
    *SHIPPED_COUPLINGS,
    *SUBAGENT_COUPLINGS,
    *MODELHOST_COUPLINGS,
    *EMAIL_COUPLINGS,
    *OVERLAY_COUPLINGS,
)
