"""The email sidecar's couplings: its four fixed answers to a refused or empty read, the four
names a declared source is written under, and the two settings that ship off.
"""

from couplings import Constant, Mention, Site, Spelling

CORE_PROVENANCE = "brain/packages/core/src/cortex_core/provenance.py"
EMAIL_COMPOSE = "docker/docker-compose.email.yml"
EMAIL_CONFIG = "brain/packages/email/src/cortex_email/config.py"
EMAIL_ERRORS = "brain/packages/email/src/cortex_email/errors.py"
EMAIL_MODULE = "docs/modules/brain-email.md"
EMAIL_SERVER = "brain/packages/email/src/cortex_email/server.py"
EMAIL_VALUES = "brain/packages/email/src/cortex_email/values.py"
OWN_TEXTS = "brain/packages/orchestrator/src/cortex_orchestrator/own_texts.py"
TOOLS_MODULE = "docs/modules/brain-tools.md"
TOOLS_REGISTRY = "brain/packages/tools/src/cortex_tools/registry.py"

SOURCE_KEY = "_SOURCE_META_KEY"

NOT_FOUND = "NOT_FOUND"

SENDER_KIND = "_SENDER_KIND"
SENDER_MEMBER = "SENDER"

KIND_FIELD = "_KIND_FIELD"
VALUE_FIELD = "_VALUE_FIELD"

_REFUSAL_SHAPE = 'f"{{name}}{{argument}!r}"'


def _refusal(sentence: str, argument: str) -> tuple[Mention, ...]:
    """The two places one refusal sentence appears, each followed by ``argument``'s repr."""
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
            "refusal on the tainting side with nothing failing (ADR-0013 decision 10)"
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
            "with nothing failing (ADR-0013 decision 10)"
        ),
        sites=(Site(EMAIL_VALUES, "FOLDER_UNKNOWN"), Site(OWN_TEXTS, "FOLDER_UNKNOWN")),
        mentions=_refusal("FOLDER_UNKNOWN", "folder"),
    ),
    Constant(
        label="the answer to a search that matched nothing",
        why=(
            "the sidecar writes this answer as a bare literal and the brain declares it to "
            "re-stamp an empty search trusted, so a rewording of the literal alone would taint "
            "every empty search with nothing failing (ADR-0013 decision 10)"
        ),
        sites=(Site(OWN_TEXTS, "NO_MATCHES"),),
        mentions=(Mention(EMAIL_SERVER, '_one_text("{value}")'),),
    ),
    Constant(
        label="the answer to reading a uid that is not there",
        why=(
            "the sidecar renders this answer over the uid and folder the call named and the "
            "brain declares the same template over the same two arguments, so a reworded answer "
            "or a renamed field alone would taint every such read with nothing failing (ADR-0013 "
            "decision 10)"
        ),
        sites=(Site(EMAIL_VALUES, NOT_FOUND), Site(OWN_TEXTS, NOT_FOUND)),
        mentions=(Mention(EMAIL_SERVER, "_one_text({name}.format(", name=NOT_FOUND),),
    ),
    Constant(
        label="the key a sidecar declares a content source under",
        why=(
            "read_email declares the message sender under this result _meta key and the brain's "
            "tool registry reads the same key into the turn's provenance, each binding it as a "
            "wire contract because the sidecar cannot import the core, so a rename on either side "
            "alone would have every message arrive without its sender and nothing fail, an absent "
            "key reading as no declaration by design (ADR-0027 decision 9)"
        ),
        sites=(Site(TOOLS_REGISTRY, SOURCE_KEY), Site(EMAIL_SERVER, SOURCE_KEY)),
        mentions=(
            Mention(TOOLS_REGISTRY, "meta.get({name})", name=SOURCE_KEY),
            Mention(EMAIL_SERVER, "{{name}: {", name=SOURCE_KEY),
            Mention(TOOLS_MODULE, '`{name}`, `"{value}"`)', name=SOURCE_KEY),
            Mention(EMAIL_MODULE, '`{name}`, `"{value}"`)', name=SOURCE_KEY),
        ),
    ),
    Constant(
        label="the kind word a sidecar declares a sender under",
        why=(
            "read_email declares its sender under this kind word and the brain admits a "
            "declaration only when the word is the value of a claimed SourceKind member, the "
            "sidecar binding it as _SENDER_KIND because it cannot import the core, so a renamed "
            "enum value alone would have claimed_source drop every declared sender and nothing "
            "fail, an unrecognized kind reading as no declaration by design (ADR-0027 "
            "decision 9)"
        ),
        sites=(Site(EMAIL_SERVER, SENDER_KIND),),
        mentions=(
            Mention(CORE_PROVENANCE, '{name} = "{value}"', name=SENDER_MEMBER),
            Mention(EMAIL_SERVER, f"{KIND_FIELD}: {{name}},", name=SENDER_KIND),
            Mention(EMAIL_MODULE, '{"kind": "{value}", "value": <From>}'),
        ),
    ),
    Constant(
        label="the field a declared source's kind is written under",
        why=(
            "read_email writes its declaration's kind word under this field and the brain's tool "
            "registry reads the same field before admitting the declaration, each binding it as "
            "a wire contract because the sidecar cannot import the core, so a field renamed on "
            "either side alone would hand claimed_source a None, drop every declared sender and "
            "fail nothing, an unreadable declaration reading as none by design (ADR-0027 "
            "decision 9)"
        ),
        sites=(Site(TOOLS_REGISTRY, KIND_FIELD), Site(EMAIL_SERVER, KIND_FIELD)),
        mentions=(
            Mention(TOOLS_REGISTRY, "fields.get({name})", name=KIND_FIELD),
            Mention(EMAIL_SERVER, "{{name}: ", name=KIND_FIELD),
            Mention(TOOLS_MODULE, '`{name}`, `"{value}"`)', name=KIND_FIELD),
            Mention(EMAIL_MODULE, '`{name}`, `"{value}"`)', name=KIND_FIELD),
        ),
    ),
    Constant(
        label="the field a declared source's value is written under",
        why=(
            "read_email writes the message sender under this field of its declaration and the "
            "brain's tool registry reads the same field into the turn's provenance, each binding "
            "it as a wire contract because the sidecar cannot import the core, so a field renamed "
            "on either side alone would hand claimed_source a None, drop every declared sender "
            "and fail nothing, an unreadable declaration reading as none by design (ADR-0027 "
            "decision 9)"
        ),
        sites=(Site(TOOLS_REGISTRY, VALUE_FIELD), Site(EMAIL_SERVER, VALUE_FIELD)),
        mentions=(
            Mention(TOOLS_REGISTRY, "fields.get({name})", name=VALUE_FIELD),
            Mention(EMAIL_SERVER, ", {name}: ", name=VALUE_FIELD),
            Mention(TOOLS_MODULE, '`{name}`, `"{value}"`)', name=VALUE_FIELD),
            Mention(EMAIL_MODULE, '`{name}`, `"{value}"`)', name=VALUE_FIELD),
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
