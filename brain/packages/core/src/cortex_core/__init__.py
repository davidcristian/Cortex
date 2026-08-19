"""Cortex brain pure core: typed logic and ports, no I/O.

A re-export barrel and nothing else. The names are not listed here: they live in the area
sub-barrels under `cortex_core._surface`, one file per area of the core, each declaring its
own `__all__`, and this file re-exports all nine wholesale. Consumers are unaffected, since
`from cortex_core import X` still reaches every public name; what changed is that a new name
costs a line in its area rather than a line here, so the surface can grow past what a single
capped file can list. `docs/modules/brain-core.md` documents the areas and their contents.
"""

from ._surface.fakes import *
from ._surface.logs import *
from ._surface.memory import *
from ._surface.ports import *
from ._surface.residency import *
from ._surface.schedule import *
from ._surface.subagents import *
from ._surface.tools import *
from ._surface.turn import *
