from correction_reads import LIST_TOOL, SEARCH_TOOL, answers_listing


def test_a_reply_that_only_lists_the_folders_is_answered_before_it_is_scored() -> None:
    assert answers_listing([LIST_TOOL])


def test_a_reply_that_searches_is_scored_as_it_is_whatever_else_it_calls() -> None:
    assert not answers_listing([SEARCH_TOOL])
    assert not answers_listing([LIST_TOOL, SEARCH_TOOL])
    assert not answers_listing([SEARCH_TOOL, LIST_TOOL])


def test_a_reply_that_neither_lists_nor_searches_is_scored_as_it_is() -> None:
    assert not answers_listing([])
    assert not answers_listing(["read_email"])
