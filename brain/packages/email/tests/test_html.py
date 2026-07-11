"""Behavior tests for html_to_text: readable prose out of HTML email bodies."""

from cortex_email.html import html_to_text


def test_strips_tags_and_decodes_entities() -> None:
    expected = "Café & tea — now"  # dashcheck: allow -- &#8212; must decode to this character
    assert html_to_text("<p>Caf&eacute; &amp; tea &#8212; now</p>") == expected


def test_block_tags_become_line_breaks() -> None:
    assert html_to_text("<p>one</p><p>two</p><div>three</div>") == "one\ntwo\nthree"


def test_br_breaks_a_line_inline_tags_do_not() -> None:
    assert html_to_text("a <b>bold</b> word<br>next line") == "a bold word\nnext line"


def test_runs_of_breaks_collapse_to_one() -> None:
    # <br/> fires start AND end handlers; blank lines are dropped, so any run is one break.
    assert html_to_text("a<br/>b<br/><br/><br/>c") == "a\nb\nc"


def test_script_style_and_head_content_is_dropped() -> None:
    html = (
        "<head><title>Skip</title><style>p { color: red }</style></head>"
        "<body><script>var x = '<p>not text</p>';</script><p>kept</p></body>"
    )
    assert html_to_text(html) == "kept"


def test_nested_dropped_containers_stay_dropped() -> None:
    # style inside head: depth 2 on the way in, still dropped after the inner container closes.
    assert html_to_text("<head><style>x</style>also dropped</head>kept") == "kept"


def test_a_stray_closing_tag_does_not_unbalance_the_drop() -> None:
    assert html_to_text("</style><p>still here</p>") == "still here"


def test_whitespace_collapses_within_lines() -> None:
    assert html_to_text("<p>a\n   lot\t of   space</p>") == "a lot of space"


def test_table_rows_and_cells_break_lines() -> None:
    html = "<table><tr><td>k1</td><td>v1</td></tr><tr><td>k2</td></tr></table>"
    assert html_to_text(html) == "k1 v1\nk2"


def test_no_prose_extracts_to_empty() -> None:
    assert html_to_text('<img src="cid:logo"><style>x{}</style>') == ""


def test_plain_text_passes_through() -> None:
    assert html_to_text("no markup at all") == "no markup at all"
