"""The couplings around one capture: what the brain asks for, holds the reply to, and waits.

One of the data files `crosscheck.py` reads as a single registry, and the eighth part to arrive. It
was split off `shippedcouplings.py` when the second spellings on already held lines brought that
file to the 300-line cap, on a seam its own text had been drawing in a comment for as long as these
entries had been in it: `# The two capture bounds that ride with a request`. Everything here is one
request's worth of shipped numbers, the pair of deadlines it runs under, and the answer to whether
the tool that sends it is offered at all (ADR-0029). Nothing in the scan asks which file an entry
sits in, so the move costs the gate nothing.

The subject is narrower than the one it left, and that is the point of naming it. `shippedcouplings`
holds whatever default the brain container ships; these hold the ones that describe a **single
capture**, which is why the edge below has a site in the other tree and the others do not: the body
encodes the picture, so the body's own suite has to size itself on the edge the brain asks for.

The same tense test settles every far side here as everywhere else (ADR-0029's compose-default
survey addendum): a sentence that becomes **wrong** when the value moves is a far side, and one
that becomes **history** is not. Two of the entries below now hold both spellings a runbook row
writes, its Default cell and the sentence in its Meaning cell restating the same number, because a
mention is a presence check and one of the two was satisfying it for both.
"""

from couplings import Constant, Mention, Site

BODY_COMPOSE = "docker/docker-compose.body.yml"
GPU_COMPOSE = "docker/docker-compose.gpu.yml"
IMAGES = "brain/packages/core/src/cortex_core/images.py"
BODY_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config_body.py"
INFERENCE_CONFIG = "brain/packages/orchestrator/src/cortex_orchestrator/config.py"
BODY_GATEWAY = "brain/packages/body_client/src/cortex_body_client/gateway.py"
BODY_CLIENT_DOC = "docs/modules/brain-body-client.md"
BODY_CORE_DOC = "docs/modules/body-core.md"
CAPTURE_BYTES = "body/crates/core/tests/capture_bytes.rs"
CAPTURE_CHECK = "docs/host/tasks/012-display-capture-path.md"
MODEL_MANAGER_DOC = "docs/modules/brain-model-manager.md"
ORCHESTRATOR_DOC = "docs/modules/brain-orchestrator.md"
GPU_RUNBOOK = "docs/runbooks/llamacpp-gpu.md"
VISION_RUNBOOK = "docs/runbooks/vision.md"
VOLUME_RUNBOOK = "docs/runbooks/body-volume.md"

# The two deadlines on the brain->body seam, and the first decimals the registry held. Each is
# declared once, in the adapter that spends it, and spelled again in four places that must move
# with it: the compose default every deployment boots on, the two runbooks that quote it to an
# operator, and the module contract a future agent reads instead of the tree. The value is
# compared as the digits it is written with rather than as a number, so a site retyped as `5`
# does not quietly agree with a stack still substituting `5.0` (see `values.py`). Each runbook
# template carries the variable's own name so it pins the row that names it, a bare `10.0`
# being a number any other row could satisfy.
CAPTURE_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the capture call's shipped deadline",
        why=(
            "the compose stack spells this default into every container it starts and two "
            "runbooks quote it as the number an operator is running, so retuning the adapter "
            "alone would leave every deployment waiting the old one (ADR-0029)"
        ),
        sites=(Site(BODY_GATEWAY, "DEFAULT_CAPTURE_TIMEOUT_S"),),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CAPTURE_TIMEOUT_S:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CAPTURE_TIMEOUT_S` | brain | `{value}` |"),
            Mention(VOLUME_RUNBOOK, "`CORTEX_BODY_CAPTURE_TIMEOUT_S` (default `{value}`)"),
            Mention(BODY_CLIENT_DOC, "`DEFAULT_CAPTURE_TIMEOUT_S = {value}`"),
        ),
    ),
    Constant(
        label="the other calls' shipped deadline",
        why=(
            "the same four places spell the short deadline the volume and notify calls run "
            "under, so the knob an operator reads and the number the adapter uses are one value "
            "or they are a documented lie (ADR-0029)"
        ),
        sites=(Site(BODY_GATEWAY, "DEFAULT_CALL_TIMEOUT_S"),),
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CALL_TIMEOUT_S:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CALL_TIMEOUT_S` | brain | `{value}` |"),
            Mention(VOLUME_RUNBOOK, "`CORTEX_BODY_CALL_TIMEOUT_S` (default `{value}`)"),
            Mention(BODY_CLIENT_DOC, "`DEFAULT_CALL_TIMEOUT_S = {value}`"),
        ),
    ),
    # The two capture bounds that ride with a request. The byte budget is the brain's half of a
    # ceiling the body enforces too, so it is a site in `seamcouplings.py` as well; here it is the
    # shipped number three deployment surfaces restate. The edge is the brain's alone.
    Constant(
        label="the capture edge's shipped default",
        why=(
            "the compose stack ships this edge into every container, two runbooks and three "
            "module contracts quote it as the brain half of the measured legibility pair, and "
            "the body's own headroom suite sizes its worst case on it, so retuning the field "
            "alone would leave every deployment asking for the old edge while the encoder was "
            "sized for the new one (ADR-0029 legibility addendum)"
        ),
        # The second site is the other tree's: `capture_bytes.rs` names the edge the brain asks
        # for and measures how much room the byte ceiling leaves at it, so a retune here alone
        # leaves that suite reporting headroom for a capture nothing requests any more.
        sites=(Site(BODY_CONFIG, "DEFAULT_CAPTURE_MAX_EDGE"), Site(CAPTURE_BYTES, "BRAIN_EDGE")),
        # Sorted by the survey's tense test: a sentence that becomes WRONG when the edge moves is
        # a far side, and one that becomes HISTORY is not. Held are the GPU override's comment
        # arguing for the token budget by naming this edge, the two files that declare the number
        # restating it in their own prose beside it, the GPU runbook's env table and the recipe
        # block under it (counted, since both state the shipped edge and losing one leaves the
        # file naming two), the vision runbook's pair-is-the-default paragraph and its cost of a
        # picture, the three module contracts, and the host check that tells an operator what a
        # stock deployment captures, which is a live instruction rather than a record: a completed
        # check's file shrinks to a heading, its status and a pointer. Left out are the GPU
        # runbook's measured arms and the byte-ceiling reading in the body contract, each true of
        # the edge it was taken at and true still after the default moves (ADR-0029 comment
        # addendum).
        #
        # The headroom suite's own three sentences are held for the reason both declaring files'
        # prose already is: it names this number as the one the brain asks for, as the reason its
        # two measured edges cost differently, and as what a maximised window is resampled to, and
        # all three are wrong about the file the day the edge is retuned. The pair the same suite
        # once asserted as digits is deliberately NOT here. `1152` is not a second spelling of the
        # edge, it is a consequence of the edge and of the fixture's aspect ratio, so a needle over
        # `(2048, 1152)` would tie two independent couplings into one and would redden on a change
        # to the display the fixture builds. That one is arithmetic in the suite instead, which
        # removes the coupling rather than holding it, and the same reading keeps the halved `1024`
        # in that file's prose out: a rung of the ladder below this edge is a consequence too.
        #
        # The last needle is the vision runbook's second spelling on the row the first one holds,
        # where the Meaning cell calls this number the brain half of the legibility pair. It
        # carries four words of that sentence, which is what the second-spelling survey settled
        # is allowed when the words are the shape that makes the sentence a claim about the
        # SHIPPED value rather than about pixels in general: cell walls pin the Default cell and
        # there is nothing else inside a table row for a needle to hold on to.
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_CAPTURE_MAX_EDGE:-{value}}"),
            Mention(BODY_COMPOSE, "defaults to {value} rather"),
            Mention(BODY_CONFIG, "defaults to **{value} rather"),
            Mention(CAPTURE_BYTES, "a {value} px capture by default"),
            Mention(CAPTURE_BYTES, "a {value} px capture costs"),
            Mention(CAPTURE_BYTES, "resampled to {value} px"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_CAPTURE_MAX_EDGE` | brain | `{value}` |"),
            Mention(VISION_RUNBOOK, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(VISION_RUNBOOK, "{value} px capture"),
            Mention(VISION_RUNBOOK, "`{value}` is the brain half"),
            Mention(GPU_RUNBOOK, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}", occurrences=2),
            Mention(GPU_COMPOSE, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(MODEL_MANAGER_DOC, "CORTEX_BODY_CAPTURE_MAX_EDGE={value}"),
            Mention(ORCHESTRATOR_DOC, "DEFAULT_CAPTURE_MAX_EDGE` ({value})"),
            Mention(BODY_CORE_DOC, "{value} px edge"),
            Mention(CAPTURE_CHECK, "at {value} px"),
        ),
    ),
    Constant(
        label="the capture byte budget's shipped default",
        why=(
            "the brain's budget defaults to the body's own ceiling, and the stack spells that "
            "number again while the vision runbook quotes it as the shipped budget and again as "
            "the top of the range the field accepts, so a tightened ceiling with either left "
            "alone would ask every deployment for more bytes than either end now allows "
            "(ADR-0029)"
        ),
        sites=(Site(IMAGES, "MAX_IMAGE_BYTES"),),
        # The second runbook needle is the other spelling on the row the first one holds. It is a
        # far side rather than a reading of one, because the field really is bounded by this
        # constant (`le=MAX_IMAGE_BYTES` in `config_body.py`), so a tightened ceiling makes the
        # stated range wrong rather than merely dated. The range syntax is the whole of what it
        # pins, no word of the sentence around it.
        mentions=(
            Mention(BODY_COMPOSE, "${CORTEX_BODY_MAX_IMAGE_BYTES:-{value}}"),
            Mention(VISION_RUNBOOK, "| `CORTEX_BODY_MAX_IMAGE_BYTES` | brain | `{value}` |"),
            Mention(VISION_RUNBOOK, "outside `1..{value}`"),
        ),
    ),
    Constant(
        label="whether capture is advertised, as shipped",
        why=(
            "the body override names the probe policy every deployment boots on and the vision "
            "runbook states it as the shipped answer, so a retuned field with the substitution "
            "left alone would keep probing where the brain had decided not to (ADR-0029)"
        ),
        sites=(Site(INFERENCE_CONFIG, "DEFAULT_VISION_MODE"),),
        # The same runbook row spells this mode a second time, and that one is deliberately NOT a
        # far side: it says what `auto` DOES, beside what `on` and `off` do, and goes on being
        # true after another mode becomes the shipped answer. It is the case that refuses a rule
        # counting every occurrence on a held line, a second spelling being no evidence of a
        # second claim about the default.
        mentions=(
            Mention(BODY_COMPOSE, '"${CORTEX_VISION:-{value}}"'),
            Mention(VISION_RUNBOOK, "| `CORTEX_VISION` | brain | `{value}` |"),
        ),
    ),
)
