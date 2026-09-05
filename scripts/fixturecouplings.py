"""The couplings inside the email probe fixture: the names the script builds and the tests read."""

from couplings import Constant, Mention, Site

PROBE_SCRIPT = "docker/dovecot/probe-mailboxes.sh"
PROBE_SUITE = "brain/packages/email/tests/test_imap_probe_live.py"

FIXTURE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the probe's account",
        why=(
            "this server resolves an account's mail home out of the login itself "
            "(`home=%{env:CORTEX_IMAP_PROBE_MAIL_ROOT}/%Lu` in docker/dovecot/probe.conf), so the "
            "segment the script builds its tree under IS the account the suite logs in as, and a "
            "rename on one side alone leaves dovecot looking in an empty home: every mailbox goes "
            "missing at once, the control among them, and the run reads as a server that lost its "
            "mail rather than as a fixture built for somebody else (ADR-0057 decision 1)"
        ),
        sites=(Site(PROBE_SUITE, "PROBE_LOGIN"),),
        mentions=(Mention(PROBE_SCRIPT, "$CORTEX_IMAP_PROBE_MAIL_ROOT/{value}", occurrences=2),),
    ),
    Constant(
        label="the probe mailbox the ACL shuts",
        why=(
            "this is the mailbox the whole second-server stack exists to produce, listed and "
            "refusing to open, and the suite asserts on it by name, so a rename in the script "
            "alone would have the suite measuring a mailbox nothing built and reading its "
            "absence as the refusal it was looking for (ADR-0057 decision 1)"
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
            "refusal nobody asked for (ADR-0057 decision 1)"
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
            "the server never lists (ADR-0056 decision 8)"
        ),
        sites=(Site(PROBE_SUITE, "NOSELECT_PARENT"),),
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/"),),
    ),
    Constant(
        label="the probe's subscribed name that no mailbox has",
        why=(
            "this name is the only thing that makes the server send RFC 5258's newer word for a "
            "name that is not a mailbox, and it exists solely as a line in the subscription file "
            "the script writes, so a rename there alone would leave the suite asking a listing "
            "about a name nothing subscribed and reading the empty answer as the flag being gone "
            "(ADR-0056 decision 9)"
        ),
        sites=(Site(PROBE_SUITE, "GHOST_SUBSCRIPTION"),),
        mentions=(Mention(PROBE_SCRIPT, "\\n\\n{value}"),),
    ),
    Constant(
        label="the probe's flagged name that opens",
        why=(
            "this is the second server's answer to the half of the flag rule that had been "
            "measured on one Bridge account and nowhere else, a name a listing calls unselectable "
            "and a SELECT opens, and the suite reads that contrast off this name in two listings "
            "at once, so a rename in the script alone would leave both readings asking about a "
            "name the server never lists (ADR-0057 decision 2)"
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
            "rather than red (ADR-0057 decision 2)"
        ),
        sites=(Site(PROBE_SUITE, "FOLLOWED_SUBSCRIPTION"),),
        mentions=(
            Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails"),
            Mention(PROBE_SCRIPT, "\\n{value}"),
        ),
    ),
    Constant(
        label="the probe mailbox holding the message it seals",
        why=(
            "this is the one read a server this repo reaches declines, a FETCH answered with a "
            "tagged NO, and the suite asserts on it by name, so a rename in the script alone "
            "would have the suite reading from a mailbox nothing built and failing on a missing "
            "folder where it was measuring a declined read (ADR-0057 decision 4)"
        ),
        sites=(Site(PROBE_SUITE, "SEALED_FOLDER"),),
        mentions=(
            Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails", occurrences=2),
            Mention(PROBE_SCRIPT, "-m {value}"),
        ),
    ),
    Constant(
        label="the uid of the message the probe seals",
        why=(
            "the file the script shuts is named after the uid dovecot gave the message, and the "
            "suite reads that uid to be refused, so a file shut under another number would leave "
            "the suite reading a message that opens and failing at the assertion that the read "
            "was declined rather than at the fixture (ADR-0057 decision 4)"
        ),
        sites=(Site(PROBE_SUITE, "SEALED_UID"),),
        mentions=(Mention(PROBE_SCRIPT, "dbox-Mails/u.{value}"),),
    ),
    Constant(
        label="the probe's child under that node",
        why=(
            "dropping an unselectable parent from an offered list is lossless only because its "
            "child is listed in its own right, which is the fact the suite reads off this name, "
            "so a rename in the script alone would leave the subtree unreachable and the "
            "argument for dropping the parent unmeasured (ADR-0056 decision 8)"
        ),
        sites=(Site(PROBE_SUITE, "NODE_CHILD"),),
        mentions=(Mention(PROBE_SCRIPT, "mailboxes/{value}/dbox-Mails"),),
    ),
)
