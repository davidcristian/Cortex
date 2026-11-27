from collections.abc import Sequence

from cortex_core import EmbedRole, HashEmbedder, InMemoryMemoryStore, MemoryRecaller, SystemClock

_ROW = "the combination on the bike lock is 3916"


class _RoleLog:
    """Embeds through the fake and keeps the role of every call."""

    def __init__(self) -> None:
        self._inner = HashEmbedder()
        self.roles: list[EmbedRole] = []

    async def embed(self, text: str, *, role: EmbedRole = EmbedRole.DOCUMENT) -> Sequence[float]:
        self.roles.append(role)
        return await self._inner.embed(text, role=role)


async def _stored() -> tuple[MemoryRecaller, _RoleLog]:
    embedder = _RoleLog()
    recaller = MemoryRecaller(InMemoryMemoryStore(), embedder, SystemClock())
    await recaller.record(_ROW, session_id="s")
    return recaller, embedder


async def test_a_recorded_text_is_embedded_as_a_document() -> None:
    _, embedder = await _stored()
    assert embedder.roles == [EmbedRole.DOCUMENT]


async def test_a_recall_embeds_its_query_as_a_query() -> None:
    recaller, embedder = await _stored()
    hits = await recaller.recall("what is the bike lock code?", k=5, session_id="s", turn_id="t")
    assert [hit.record.text for hit in hits] == [_ROW]
    assert embedder.roles == [EmbedRole.DOCUMENT, EmbedRole.QUERY]


async def test_a_nearest_search_embeds_its_query_as_a_query() -> None:
    recaller, embedder = await _stored()
    rows = await recaller.nearest("forget the bike lock", session_id="s", limit=5)
    assert [row.text for row in rows] == [_ROW]
    assert embedder.roles == [EmbedRole.DOCUMENT, EmbedRole.QUERY]


async def test_the_fake_embeds_a_text_alike_in_both_roles() -> None:
    embedder = HashEmbedder()
    query = await embedder.embed(_ROW, role=EmbedRole.QUERY)
    assert query == await embedder.embed(_ROW, role=EmbedRole.DOCUMENT)
