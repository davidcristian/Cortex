# A token written in .env reaches compose and never reaches just

**Status:** open, waiting for its trigger
**Trigger:** an operator keeps `CORTEX_SEAM_TOKEN` in `.env` rather than in the environment, since
that is the first moment the two readers of that file disagree about what is configured. Two
readings decide it: `grep -c '^CORTEX_SEAM_TOKEN=' .env` in the checkout (no `.env` exists on
2026-09-17), and `grep -n '^set' justfile`, which prints nothing while no `dotenv-load` has been
added.
**Area:** rpc-auth
**Origin:** [ADR-0016](../../adr/ADR-0016-shared-token.md)
**Verified:** 2026-09-17

`docker/docker-compose.yml` documents the token as passed through from the host environment or
`.env`, and compose does read that file: `just up` against a `.env` holding `CORTEX_SEAM_TOKEN`
serves a token-protected brain. `just` reads nothing of the kind (the justfile sets no
`dotenv-load`), so the same file leaves the live suite's own process without a token, and it must
present one to get past the brain's interceptor. The operator's reasonable reading, that one file
configures the stack, is half true, and the false half costs them a suite that cannot
authenticate. The guard in `just seam-health` names this where they meet it, which is a signpost
rather than a fix.

`set dotenv-load := true` is a justfile-wide setting: it would put every variable in that file into
the environment of every recipe, including `just check`, which must not vary with a file git does
not track. A narrower shape, one recipe sourcing the file itself, trades that risk for a second
reader of an untracked file, written by hand, that nothing compares with compose's own rules for
quoting and precedence.

The decision is which reader is authoritative for a recipe that is not compose: either the justfile
reads the file under a rule narrow enough that `just check` cannot inherit from it, or the
documentation stops offering `.env` as a way to configure anything except the compose stack.

## History

- 2026-08-25: opened by the pass that gave `just seam-health` a checked precondition
  ([ADR-0016](../../adr/ADR-0016-shared-token.md) decision 8).
- 2026-09-11: both readers were run against a throwaway `.env` holding
  `CORTEX_SEAM_TOKEN=probe-token-441`, written into the checkout for the length of the check and
  removed after it. `docker compose --project-directory . -f docker/docker-compose.yml config`
  rendered `CORTEX_SEAM_TOKEN: probe-token-441` into the brain service's environment, and
  `just seam-health`, run with the variable unset in the environment and that same `.env` in place,
  stopped at its guard with "CORTEX_SEAM_TOKEN is unset". The justfile has no `set` line. No `.env`
  exists in this checkout, so the trigger has not fired here. The split is now stated in two
  places, the guard's own message and `docs/runbooks/local-dev-wsl.md`, and the runbook offers
  `.env` for the compose stack alone.
- 2026-09-17: not fired, and settled without writing into the checkout. A scratch directory held a
  `.env` with `CORTEX_SEAM_TOKEN=probe-token-441` and a copy of the justfile. With the variable
  unset, `docker compose --project-directory <scratch> -f docker/docker-compose.yml config`
  rendered `CORTEX_SEAM_TOKEN: probe-token-441` into the brain service, and rendered `""` with that
  file moved aside, so the file is what supplied it.
  `just --justfile <scratch>/justfile --working-directory <scratch> seam-health` stopped at its
  guard with "CORTEX_SEAM_TOKEN is unset". Three commits dated 2026-09-11 or later touched the
  justfile and it still has no `set` line, and the checkout has no `.env`. The split is wider than
  the live suite: `just brain-serve` runs the brain on the host with no `env_file` in any settings
  class, and the host body reads the token from its own process environment (`converse.rs:192`,
  `brain.rs:106`, `body_server.rs:59` under `body/app/src-tauri/src/`), so `.env` configures the
  compose brain and nothing else in the repo. The runbook's sentence names `just` as the reader
  that skips the file, which takes in `brain-serve`, and says nothing about the body, which would
  need a token exported wherever it is launched whatever `.env` holds.
