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
purpose. Nor the login's password, which is the account's own name spent a second time in one
expression, `nopassword=y` leaving nothing on the server to agree with it: a value spelled twice in
one file under one constant is not two places, and the far side here is an absence.

**And the mail root above the account is not here, for a reason worth writing down.** `/srv/mail`
is spelled in the script, in `docker/dovecot/probe.conf` and in the compose tmpfs that makes the
store throwaway, and those three really must agree. No tree declares it. This scan compares a
declaration against the places restating one, and inventing a declaration in a suite that has no
use for the value would be the gate editing the contract it watches, so the prefix rides along
inside the account's own template as shape rather than as a value of its own. That leaves the
compose tmpfs untied, which is the same shape of gap the compose defaults had before a gate of
their own was written for them.
"""

from couplings import Constant, Mention, Site

PROBE_SCRIPT = "docker/dovecot/probe-mailboxes.sh"
PROBE_SUITE = "brain/packages/email/tests/test_imap_probe_live.py"

FIXTURE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the probe's account",
        why=(
            "this server resolves an account's mail home out of the login itself "
            "(`home=/srv/mail/%Lu` in docker/dovecot/probe.conf), so the segment the script "
            "builds its tree under IS the account the suite logs in as, and a rename on one side "
            "alone leaves dovecot looking in an empty home: every mailbox goes missing at once, "
            "the control among them, and the run reads as a server that lost its mail rather "
            "than as a fixture built for somebody else (ADR-0022 two-server addendum)"
        ),
        sites=(Site(PROBE_SUITE, "PROBE_LOGIN"),),
        # Two occurrences and one set: the home the tree is built under, and the same home handed
        # to `chown` seven lines later. Unlike the guarded mailbox's pair, a half applied rename
        # here is not silent, `set -eu` stopping the script on a chown of a directory nothing
        # made. It is only late: nothing runs this fixture until somebody measures, which is the
        # whole reason this part exists, so the count moves that failure to the gate that runs.
        mentions=(Mention(PROBE_SCRIPT, "/srv/mail/{value}", occurrences=2),),
    ),
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
        label="the probe's subscribed name that no mailbox has",
        why=(
            "this name is the only thing that makes the server send RFC 5258's newer word for a "
            "name that is not a mailbox, and it exists solely as a line in the subscription file "
            "the script writes, so a rename there alone would leave the suite asking a listing "
            "about a name nothing subscribed and reading the empty answer as the flag being gone "
            "(ADR-0022 newer-spelling addendum)"
        ),
        sites=(Site(PROBE_SUITE, "GHOST_SUBSCRIPTION"),),
        # The name as the file's first content line, straight after the empty namespace-prefix
        # line, which is the whole of what the script says about it: there is no directory to pin,
        # the absence of one being the point. The line's own end is deliberately not pinned. It
        # was once, when this was the only subscription, and the needle went stale the moment a
        # second name was written under it: what a subscription needs is a line of its own, not
        # the last one in the file.
        mentions=(Mention(PROBE_SCRIPT, "\\n\\n{value}"),),
    ),
    Constant(
        label="the probe's flagged name that opens",
        why=(
            "this is the second server's answer to the half of the flag rule that had been "
            "measured on one Bridge account and nowhere else, a name a listing calls unselectable "
            "and a SELECT opens, and the suite reads that contrast off this name in two listings "
            "at once, so a rename in the script alone would leave both readings asking about a "
            "name the server never lists (ADR-0022 flagged-name-that-opens addendum)"
        ),
        sites=(Site(PROBE_SUITE, "FEIGNED_FOLDER"),),
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails"),),
    ),
    Constant(
        label="the probe's subscribed child that flags its parent",
        why=(
            "the parent above carries `\\Noselect` only because this child is subscribed and it "
            "is not, so this name is the entire cause of the flag, and a rename that moved the "
            "mailbox and left the subscription line, or the reverse, would take the flag off the "
            "parent while every mailbox the suite names still existed: the reading would go quiet "
            "rather than red (ADR-0022 flagged-name-that-opens addendum)"
        ),
        sites=(Site(PROBE_SUITE, "FOLLOWED_SUBSCRIPTION"),),
        # Two mentions rather than two occurrences of one, the halves being different shapes: the
        # mailbox that makes the name real, and the subscription line that makes it flag its
        # parent. Either alone is a fixture that builds something the suite is not measuring.
        mentions=(
            Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails"),
            Mention(PROBE_SCRIPT, "\\n{value}"),
        ),
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
