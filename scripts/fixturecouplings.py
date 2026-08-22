"""The couplings inside a measurement fixture: what a stack is built to hold, and what names it.

One of the data files `crosscheck.py` reads as a single registry, and the seventh part. Like
`emailcouplings.py` before it, it arrived as a subject rather than as a split under the 300-line
cap: a new part is a data file plus one line in `registry.py`, and the scan never learns the
registry grew. The subject is the one no other part holds. Every other part ties something the
repo **ships**, a default a container boots on or a value one tree's code hands another's. These
tie something the repo **measures with**: a stack that exists only so a suite can watch a real
server answer, and the suite that names what the stack was built to contain.

**Why a fixture needs a gate more than a shipped value does, not less.** A shipped default has a
suite that runs on every commit and would notice. The suite here is `integration`-marked, so it
never runs in CI and runs on a host only when somebody chooses to measure. Rename a mailbox in the
script and every gate stays green, for months, while the fixture builds one tree and the suite
asks about another; the failure surfaces on the next measurement, worded as a server behaving
oddly rather than as a fixture that moved. This scan is the only thing that reads both files.

**What is deliberately not here.** Neither the probe's address nor its port: `just
email-folder-probe` reads both back off docker, the publish when it answers and the container's
own address when it does not, so neither is written down anywhere a rename could strand. Nor the
name the suite invents to be refused, `Nonexistent`, whose whole point is that the script does not
build it; a coupling needs two places holding one value, and that one is a value with one place on
purpose.
"""

from couplings import Constant, Mention, Site

PROBE_SCRIPT = "docker/dovecot/probe-mailboxes.sh"
PROBE_SUITE = "brain/packages/email/tests/test_imap_probe_live.py"

FIXTURE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the probe mailbox the ACL shuts",
        why=(
            "this is the mailbox the whole second-server stack exists to produce, listed and "
            "refusing to open, and the suite asserts on it by name, so a rename in the script "
            "alone would have the suite measuring a mailbox nothing built and reading its "
            "absence as the refusal it was looking for (ADR-0022 two-server addendum)"
        ),
        sites=(Site(PROBE_SUITE, "GUARDED_FOLDER"),),
        # Two occurrences and one set: the mailbox directory, and the ACL file written inside it.
        # A rename that moved the first and left the second puts the ACL under a directory
        # dovecot never reads, and the mailbox then opens like any other. The suite would still
        # find the name listed and would fail on the refusal, which is a measurement wasted on a
        # fixture fault; the count is what refuses the half applied rename here.
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails", occurrences=2),),
    ),
    Constant(
        label="the probe folder that opens",
        why=(
            "the control the other assertions rest on, since a server refusing everything would "
            "satisfy every refusal test in the suite, so a rename in the script alone would "
            "turn the one test that proves the login and the read path work into another "
            "refusal nobody asked for (ADR-0022 two-server addendum)"
        ),
        sites=(Site(PROBE_SUITE, "REAL_FOLDER"),),
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails"),),
    ),
    Constant(
        label="the probe's listed node that is no mailbox",
        why=(
            "the node is unselectable because the script gives it a child and no mailbox of its "
            "own, and the suite names it to prove a listed name can be one no SELECT opens, so "
            "a rename of that parent segment alone would leave the suite asking about a name "
            "the server never lists (ADR-0022 flagged-and-refused addendum)"
        ),
        sites=(Site(PROBE_SUITE, "NOSELECT_PARENT"),),
        # The segment as a parent, which is the whole of what the script says about this name:
        # the node exists only because a path runs through it, and there is no absence a needle
        # could pin.
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/"),),
    ),
    Constant(
        label="the probe's child under that node",
        why=(
            "dropping an unselectable parent from an offered list is lossless only because its "
            "child is listed in its own right, which is the fact the suite reads off this name, "
            "so a rename in the script alone would leave the subtree unreachable and the "
            "argument for dropping the parent unmeasured (ADR-0022 flagged-and-refused addendum)"
        ),
        sites=(Site(PROBE_SUITE, "NODE_CHILD"),),
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails"),),
    ),
)
