"""The email sidecar's couplings: two hatches, a switch, four texts, and a declaration's four words.

One of the data files `crosscheck.py` reads as a single registry, added the way `registry.py` was
built to take one: a data file plus one line there, with nothing in the scan naming the registry's
parts. The subject is the one env surface no other part holds, the read-only IMAP sidecar's own,
and the three variables in it whose default is an answer rather than a number; since the own-text
overlay (ADR-0013 own-text addendum), also the four answers the sidecar composes without reading
a message, which the brain restates in `cortex_orchestrator/own_texts.py` and re-stamps trusted
on byte equality. The sidecar cannot import the core and the brain does not import the sidecar,
so the restatement is held here the way a cross-language constant is: a rewording on either side
alone fails this gate rather than silently landing that answer on the tainting side.

The key `read_email` declares a message's sender under is held here on the same argument. The
sidecar writes `_meta["cortex/source"]` and the brain's tool registry reads it, each binding the
key as `_SOURCE_META_KEY` under a comment calling it a wire contract, and a rename on either side
alone would have every message arrive without its sender while nothing failed, since an absent
key reads as no declaration by design. The entry holds the two bindings equal, holds each module's
one spend of the key to its own binding, so a read or a write that stops going through the
binding is caught with the binding still in place, and holds the two module contracts that quote
the binding and the key together. Neither suite's pin of the literal is registered: a pin fails
on its own under a one-sided rename, and a rename that carries its pin along is what the two
sites catch (ADR-0029 declared-source-key addendum).

The kind word that declaration carries, `sender`, is held on the same argument. The brain admits a
declaration only when its kind is the value of a claimed `SourceKind` member, and that member is
indented inside its class, where the Python declaration syntax, anchored at column 0, reads no
site. So the sidecar binds the word once at module level as `_SENDER_KIND`, the entry's one site,
and the enum member is a mention rendering both its name and the value, the form the registry has
for a far side the scan cannot read a declaration out of. The server's one spend of the word is
held to its binding, and the module contract's quotation of the declaration's shape is held with
the word in it (ADR-0029 declared-kind-word addendum).

The two field names the declaration is written under, `kind` and `value`, are held on the same
argument as the key and in the key's shape: the sidecar writes them and the brain's tool registry
reads them, so each module binds both as `_KIND_FIELD` and `_VALUE_FIELD`, the two bindings of
each name are an entry's sites, and each module's spend of its own binding is a mention. A field
renamed on one side alone would hand `claimed_source` a `None` in that position, which it answers
with no declaration, the silence the key's entry names a third time (ADR-0029 declaration-fields
addendum).

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

# The binding both modules declare the declared-source key under, spelled once because the entry
# names it at both sites and at each module's spend of its own binding.
SOURCE_KEY = "_SOURCE_META_KEY"

# The binding the server declares the kind word under, and the enum member the core admits it as.
# The member is spelled here rather than read, since the scan has no declaration syntax for a
# name bound inside a class body; it is the name half of a mention that renders both halves.
SENDER_KIND = "_SENDER_KIND"
SENDER_MEMBER = "SENDER"

# The bindings both modules declare the declaration's two field names under, spelled once each
# because an entry names its field at both sites and at each module's spend of its own binding.
KIND_FIELD = "_KIND_FIELD"
VALUE_FIELD = "_VALUE_FIELD"

# The shape both refusals are rendered in, the sentence followed by the repr of the argument the
# brain sent, pinned where the sidecar composes it and where the brain renders its expectation. A
# refusal that stopped quoting its argument, or quoted it without the repr, would no longer be the
# bytes the brain expects, and this is what says so.
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
            # Each module's one spend of the key, held to its own binding: a read or a write that
            # stopped going through the binding would leave both sites agreeing on a key neither
            # module used. The second template is a plain string, so its doubled brace is the
            # dict's own brace followed by the name placeholder.
            Mention(TOOLS_REGISTRY, "meta.get({name})", name=SOURCE_KEY),
            Mention(EMAIL_SERVER, "{{name}: {", name=SOURCE_KEY),
            # Both module contracts quote the binding and the key together, in this one shape.
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
            "fail, an unrecognized kind reading as no declaration by design (ADR-0027 sidecar "
            "addendum)"
        ),
        sites=(Site(EMAIL_SERVER, SENDER_KIND),),
        mentions=(
            # The enum member, rendered name and value together because the scan cannot read a
            # binding inside a class body as a site: the needle is built from the server's value
            # and looked for in the core, so either side moving alone leaves it unfound.
            Mention(CORE_PROVENANCE, '{name} = "{value}"', name=SENDER_MEMBER),
            # The server's one spend of the word, held to its own binding for the reason the key's
            # spend is above. The field it is written under is a binding of its own, held by the
            # kind-field entry below, so its name is this needle's shape.
            Mention(EMAIL_SERVER, f"{KIND_FIELD}: {{name}},", name=SENDER_KIND),
            # The module contract quotes the declaration's shape with the word in it.
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
            "fail nothing, an unreadable declaration reading as none by design (ADR-0027 sidecar "
            "addendum)"
        ),
        sites=(Site(TOOLS_REGISTRY, KIND_FIELD), Site(EMAIL_SERVER, KIND_FIELD)),
        mentions=(
            # Each module's one spend of the field, held to its own binding as the key's is: the
            # registry's read, and the server's write as the inner mapping's first key.
            Mention(TOOLS_REGISTRY, "fields.get({name})", name=KIND_FIELD),
            Mention(EMAIL_SERVER, "{{name}: ", name=KIND_FIELD),
            # Both module contracts quote the binding and the field together, in the key's shape.
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
            "sidecar addendum)"
        ),
        sites=(Site(TOOLS_REGISTRY, VALUE_FIELD), Site(EMAIL_SERVER, VALUE_FIELD)),
        mentions=(
            # The same two spends: the registry's read, and the server's write as the inner
            # mapping's second key, after the separator.
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
