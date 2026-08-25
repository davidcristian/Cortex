# A seam token written in .env reaches compose and never reaches just

**Status:** open, fix when it bites
**Trigger:** an operator keeps the seam token in `.env` rather than in the environment, since that
is the first moment the two readers of that file disagree about what is configured.
**Area:** seam-auth
**Origin:** [ADR-0016](../../adr/ADR-0016-seam-token.md)

Opened 2026-08-25 by the pass that gave `just seam-health` a checked precondition
([ADR-0016 addendum on the checked precondition](../../adr/ADR-0016-seam-token.md)).

`docker/docker-compose.yml` documents the token as "passed through from the host env / .env", and
compose does read that file: `just up` against a `.env` holding `CORTEX_SEAM_TOKEN` serves a
token-protected brain. `just` reads nothing of the kind (the justfile sets no `dotenv-load`), so
the same file leaves the live suite's own process token-free, and it must present the token to get
past the brain's interceptor at all. The operator's reasonable reading, one file configures the
stack, is half true, and the half that is false costs them a suite that cannot authenticate.

The guard now names this where they meet it, in the message `just seam-health` prints when the
variable is empty. That is a signpost rather than a fix.

**Why it was left.** `set dotenv-load := true` is a justfile-wide setting: it would put every
variable in that file into the environment of every recipe, including `just check`, which is the
gate and must not vary with a file git does not track. A narrower shape (one recipe sourcing the
file itself) trades that risk for a second reader of an untracked file, spelled by hand, that
nothing holds to compose's own rules for quoting and precedence.

**What would close it.** Decide which reader is authoritative for a recipe that is not compose:
either the justfile learns the file under a rule narrow enough that the gate cannot inherit from
it, or the documentation stops offering `.env` as a way to configure anything except the compose
stack and says the environment is where the body-side checks read from. The second costs nothing to
implement and something to write, which is the trade to make deliberately rather than by default.
