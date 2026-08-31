"""The couplings around the email sidecar's shipped answers: the two hatches and the switch.

One of the data files `crosscheck.py` reads as a single registry, added the way `registry.py` was
built to take one: a data file plus one line there, with nothing in the scan naming the registry's
parts. The subject is the one env surface no other part holds, the read-only IMAP sidecar's own,
and the three variables in it whose default is an answer rather than a number.

Each of the three is off for a safety reason rather than a tuning one: two are the TLS escape
hatches that accept a self-signed certificate on loopback, and the third is the write capability
that turns a read-only server into one that can send mail. A default flipping open in the compose
stack while the field it restates still declares shut is the drift nobody would notice, since every
read path goes on working and only the guarantee is gone.

They could not be registered until the reducer could read a boolean, and the compose stack cannot
spell the answer the way Python declares it: `False` there is `false` here. So each mention takes
`Spelling.LOWERED`, the second re-spelling this registry has and the first that is faithful, two
answers folding to two words rather than to one (ADR-0029's boolean addendum).
"""

from couplings import Constant, Mention, Site, Spelling

EMAIL_COMPOSE = "docker/docker-compose.email.yml"
EMAIL_CONFIG = "brain/packages/email/src/cortex_email/config.py"

EMAIL_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="whether the TLS escape hatches ship open",
        why=(
            "one shipped answer covers the reader's hatch and the sender's, and the email "
            "override spells it again for each, so a substitution flipped to true with the field "
            "left alone would have every composed deployment accepting whatever certificate the "
            "far end offered while the config still promised otherwise (ADR-0009/0022)"
        ),
        sites=(Site(EMAIL_CONFIG, "DEFAULT_TLS_INSECURE"),),
        mentions=(
            Mention(
                EMAIL_COMPOSE,
                "${CORTEX_EMAIL_IMAP_TLS_INSECURE:-{value}}",
                spelling=Spelling.LOWERED,
            ),
            Mention(
                EMAIL_COMPOSE,
                "${CORTEX_EMAIL_SMTP_TLS_INSECURE:-{value}}",
                spelling=Spelling.LOWERED,
            ),
        ),
    ),
    Constant(
        label="whether the send path ships enabled",
        why=(
            "the sidecar is byte for byte the read-only server until this switch is thrown, and "
            "the override names the answer every deployment boots on, so a substitution turned "
            "on alone would register the write tool in every composed stack while the field a "
            "reader checks still said the server could only read (ADR-0022)"
        ),
        sites=(Site(EMAIL_CONFIG, "DEFAULT_SEND_ENABLED"),),
        mentions=(
            Mention(
                EMAIL_COMPOSE,
                "${CORTEX_EMAIL_SEND_ENABLED:-{value}}",
                spelling=Spelling.LOWERED,
            ),
        ),
    ),
)
