"""Area sub-barrels behind the ``cortex_core`` barrel.

Private on purpose: `cortex_core` re-exports each module here wholesale, so the import path
for every public core name stays `cortex_core` and no consumer names `_surface`. The split
exists because one flat barrel of re-exports had reached the repo's 300-line cap, and it is
one file per area of the core rather than one per defining module, so a new public name has
an obvious home and the cap now bounds an area rather than the whole surface.
"""
