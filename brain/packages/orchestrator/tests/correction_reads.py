"""How the correction rows read a reply: which listing is answered before a query is scored."""

from collections.abc import Sequence

LIST_TOOL = "list_folders"
SEARCH_TOOL = "search_emails"


def answers_listing(names: Sequence[str]) -> bool:
    """Whether a reply listed the folders without searching, so the listing is answered first."""
    return LIST_TOOL in names and SEARCH_TOOL not in names
