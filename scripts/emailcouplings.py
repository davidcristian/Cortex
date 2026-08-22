"""The couplings around the email sidecar's shipped answers: the two hatches and the switch."""

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
