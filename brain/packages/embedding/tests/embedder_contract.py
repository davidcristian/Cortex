"""The `Embedder` contract, run over every implementation (AGENTS.md: ports before adapters).

The port is one method wide, so its promises are easy to state and were, until this file, stated
twice: once by the core's suite over `HashEmbedder` and once by the adapter's own suite over
`LlamaCppEmbedder`. What both suites were describing is a vector the ranking arithmetic can use,
and the four checks below are that description, driven over both implementations by
`test_embedder_contract.py`.

The port needs one condition of the world no method can create, so each fixture supplies it as a
knob: **the backend cannot answer**. A vector is the only thing `embed` returns, which leaves the
failure channel invisible to every other check, and it is the channel the port names.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import Embedder, EmbedderError

# One text embedded twice, and a second one embedded between them: enough to tell an
# implementation that answers from the text apart from one that answers from a counter.
_TEXT = "the sky is blue"
_OTHER = "a fact worth remembering"


@dataclass(frozen=True, slots=True)
class EmbedderUnderTest:
    """One implementation plus the one way a test may take its backend away.

    `break_backend` makes every later `embed` impossible. A fake has no backend to break, so it
    satisfies the knob by being scripted to raise what the port owes for a backend that cannot
    answer, which is the honest widening the vision probe's contract already uses: the check
    states what an implementation must *do* when it cannot embed, not what went wrong.
    """

    embedder: Embedder
    break_backend: Callable[[], None]


type Check = Callable[[EmbedderUnderTest], Awaitable[None]]


async def text_embeds_to_a_vector_of_real_numbers(under_test: EmbedderUnderTest) -> None:
    """The answer is a non-empty sequence of floats, because ranking multiplies and sums it.

    A vector of JSON integers or of strings would survive the port and fail in the middle of the
    cosine, which is a `TypeError` from a ranking function rather than an error at the boundary
    that produced it. An empty one is worse: it ranks silently, every candidate scoring zero.
    """
    vector = await under_test.embedder.embed(_TEXT)
    assert len(vector) > 0
    assert all(type(value) is float for value in vector)


async def every_text_embeds_at_one_width(under_test: EmbedderUnderTest) -> None:
    """The width belongs to the deployment's model, never to the text that was embedded.

    A query is embedded on one call and compared against vectors embedded on earlier ones, and
    the comparison zips them strictly. A width that moved with the text would therefore not rank
    badly, it would raise from inside the store on the first recall that met a shorter memory.
    """
    widths = {
        len(await under_test.embedder.embed(_TEXT)),
        len(await under_test.embedder.embed(_OTHER)),
        len(await under_test.embedder.embed("")),
    }
    assert len(widths) == 1


async def the_same_text_embeds_the_same_way(under_test: EmbedderUnderTest) -> None:
    """One text always embeds to one vector, and an embedding between them changes nothing.

    This is what makes a stored memory its own strongest match, and it is a statement about the
    port rather than about the model: `embed` is a function of its argument, so an implementation
    holding a cursor, a session, or any other state across calls fails here.
    """
    first = list(await under_test.embedder.embed(_TEXT))
    await under_test.embedder.embed(_OTHER)
    assert list(await under_test.embedder.embed(_TEXT)) == first


async def a_backend_that_cannot_answer_raises_embedder_error(
    under_test: EmbedderUnderTest,
) -> None:
    """The port has one failure channel and every implementation owes it.

    Nothing in the core catches an `EmbedderError` today, so what this pins is the *type* a
    caller would have to catch: an adapter letting its transport's own exception through would
    make a recall failure indistinguishable from a bug, and a fake that cannot fail at all cannot
    stand in for the adapter in any test of the path.
    """
    under_test.break_backend()
    try:
        await under_test.embedder.embed(_TEXT)
    except EmbedderError:
        return
    msg = "a broken backend embedded anyway"
    raise AssertionError(msg)


ALL_CHECKS: Sequence[Check] = (
    text_embeds_to_a_vector_of_real_numbers,
    every_text_embeds_at_one_width,
    the_same_text_embeds_the_same_way,
    a_backend_that_cannot_answer_raises_embedder_error,
)
