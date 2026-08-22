"""The couplings inside a measurement fixture: what a stack is built to hold, and what names it."""

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
        # The name as the file's one content line, which is the whole of what the script says
        # about it: there is no directory to pin, the absence of one being the point.
        mentions=(Mention(PROBE_SCRIPT, "\\n\\n{value}\\n"),),
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
