"""The couplings around the email sidecar's answers: two hatches, a switch, four texts and a key."""

from couplings import Constant, Mention, Site, Spelling

EMAIL_COMPOSE = "docker/docker-compose.email.yml"
EMAIL_CONFIG = "brain/packages/email/src/cortex_email/config.py"
EMAIL_ERRORS = "brain/packages/email/src/cortex_email/errors.py"
EMAIL_MODULE = "docs/modules/brain-email.md"
EMAIL_SERVER = "brain/packages/email/src/cortex_email/server.py"
EMAIL_VALUES = "brain/packages/email/src/cortex_email/values.py"
OWN_TEXTS = "brain/packages/orchestrator/src/cortex_orchestrator/own_texts.py"
TOOLS_MODULE = "docs/modules/brain-tools.md"
TOOLS_REGISTRY = "brain/packages/tools/src/cortex_tools/registry.py"

# The binding both modules declare the declared-source key under, spelled once because the entry
# names it at both sites and at each module's spend of its own binding.
SOURCE_KEY = "_SOURCE_META_KEY"

_REFUSAL_SHAPE = 'f"{{name}}{{argument}!r}"'


def _refusal(sentence: str, argument: str) -> tuple[Mention, ...]:
    """The two spends of one refusal sentence, each rendering it followed by ``argument``'s repr."""
    template = _REFUSAL_SHAPE.replace("{argument}", argument)
    return (
        Mention(EMAIL_ERRORS, template, name=sentence),
        Mention(OWN_TEXTS, template, name=sentence),
    )


EMAIL_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the sentence a refused search answers with",
        why=(
            "the brain re-stamps a search_emails result trusted only when its bytes are this "
            "sentence followed by the repr of the query the brain sent, and the sidecar composes "
            "that answer from its own copy, so a rewording on either side alone would land every "
            "refusal on the tainting side with nothing failing (ADR-0013 own-text addendum)"
        ),
        sites=(Site(EMAIL_VALUES, "SEARCH_REFUSED"), Site(OWN_TEXTS, "SEARCH_REFUSED")),
        mentions=_refusal("SEARCH_REFUSED", "query"),
    ),
    Constant(
        label="the sentence an unknown folder answers with",
        why=(
            "both folder-taking tools answer a guessed folder with this sentence followed by the "
            "repr of the folder the brain sent, and the brain re-stamps that answer trusted on "
            "those bytes alone, so a rewording on either side alone would taint every such turn "
            "with nothing failing (ADR-0013 own-text addendum)"
        ),
        sites=(Site(EMAIL_VALUES, "FOLDER_UNKNOWN"), Site(OWN_TEXTS, "FOLDER_UNKNOWN")),
        mentions=_refusal("FOLDER_UNKNOWN", "folder"),
    ),
    Constant(
        label="the answer to a search that matched nothing",
        why=(
            "the sidecar writes this answer as a bare literal and the brain declares it to "
            "re-stamp an empty search trusted, so a rewording of the literal alone would taint "
            "every empty search with nothing failing (ADR-0013 own-text addendum)"
        ),
        sites=(Site(OWN_TEXTS, "NO_MATCHES"),),
        mentions=(Mention(EMAIL_SERVER, '_one_text("{value}")'),),
    ),
    Constant(
        label="the answer to reading a uid that is not there",
        why=(
            "the sidecar writes this answer as an f-string over its own parameter names and the "
            "brain declares the same text as a format over the call's arguments, so a reworded "
            "answer or a renamed parameter alone would taint every such read with nothing "
            "failing (ADR-0013 own-text addendum)"
        ),
        sites=(Site(OWN_TEXTS, "NOT_FOUND"),),
        mentions=(Mention(EMAIL_SERVER, '_one_text(f"{value}")'),),
    ),
    Constant(
        label="the key a sidecar declares a content source under",
        why=(
            "read_email declares the message sender under this result _meta key and the brain's "
            "tool registry reads the same key into the turn's provenance, each binding it as a "
            "wire contract because the sidecar cannot import the core, so a rename on either side "
            "alone would have every message arrive without its sender and nothing fail, an absent "
            "key reading as no declaration by design (ADR-0027 sidecar addendum)"
        ),
        sites=(Site(TOOLS_REGISTRY, SOURCE_KEY), Site(EMAIL_SERVER, SOURCE_KEY)),
        mentions=(
            Mention(TOOLS_REGISTRY, "meta.get({name})", name=SOURCE_KEY),
            Mention(EMAIL_SERVER, "{{name}: {", name=SOURCE_KEY),
            # Both module contracts quote the binding and the key together, in this one shape.
            Mention(TOOLS_MODULE, '`{name}`, `"{value}"`)', name=SOURCE_KEY),
            Mention(EMAIL_MODULE, '`{name}`, `"{value}"`)', name=SOURCE_KEY),
        ),
    ),
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
