# The NVFP4 files for the deep tier have no baseline rows

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-17

On 2026-11-17 the models mount gained two files meant for the deep tier, both in NVFP4, a 4-bit
floating point weight format:

- `esatapedico/Qwen3.8-27B-NVFP4-MTP-GGUF`, a 17.84 GB download.
- `esatapedico/Gemma-4-31B-IT-NVFP4-GGUF`, a 17.99 GB download.

The model baseline of 2026-11-16 was drawn before they arrived, so it has no row for either. Nothing
in the repo names NVFP4, and no tier default points at these files.

What the baseline measured for the same two models in the files the mount held then, on the 24 GB
card with an 18,177 MiB model budget and a 16-bit context cache:

- `Qwen3.8-27B-UD-Q4_K_M.gguf`, 16.56 GB: fits whole up to a 24K context with its draft layer at
  draft lengths 1 to 3, and up to 40K without drafting.
- `gemma-4-31B-it-qat-UD-Q4_K_XL.gguf`, 17.29 GB: does not fit whole at any context. It runs with
  part of its layers in RAM.

Both NVFP4 files are larger than the files they would replace, so on size alone each leaves less
room for context.

What is not known:

- Whether the engine build the model host runs loads an NVFP4 file, and whether it computes the
  format on the card or converts it.
- The card memory each file takes, and so the largest context that fits.
- The rate, with and without a drafter, and which draft length is best.
- Whether the Gemma repository has a drafter file, as the Qwen one's name says it does.

What would close it: baseline rows for both files, drawn the way the 2026-11-16 baseline was (the
same budget, a 16-bit context cache, the top-down search for the largest context, the draft ladder
and its stop rule, a split run with RAM when the file does not fit whole), set beside the rows of
the two files above, and then a decision in ADR-0004 on which file the deep tier names.

This comes before the 8-bit cache rows of
[R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md), so that set includes
these files.

## History

- 2026-11-17: filed when the user started the two downloads, as the second of three follow-ups to
  the model baseline.
