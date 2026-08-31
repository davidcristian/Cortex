"""Area sub-barrels behind the ``cortex_core`` barrel.

Private: `cortex_core` re-exports each module here wholesale, so the import path for every
public core name stays `cortex_core`. The split exists because one flat barrel of re-exports
had reached the repo's 300-line cap. It is one file per area of the core rather than one per
defining module, so the cap bounds an area rather than the whole public surface.
"""
