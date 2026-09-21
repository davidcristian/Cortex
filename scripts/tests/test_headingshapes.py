import re
from pathlib import Path

import pytest

import backloganchors
import headingshapes
from headingshapes import Unsluggable

ROOT = Path(__file__).resolve().parents[2]


def test_headings_numbers_every_level_and_skips_what_only_looks_like_one() -> None:
    text = (
        "# One\n"
        "###### Six deep\n"
        "####### Seven is not a heading\n"
        "#not a heading either\n"
        "Prose about # something.\n"
        "## Trailing spaces  \n"
    )
    assert headingshapes.headings(text) == [
        (1, "One"),
        (2, "Six deep"),
        (6, "Trailing spaces"),
    ]


def test_headings_ignores_a_hash_inside_a_fenced_block() -> None:
    text = "# Real\n```bash\n# start the stack\n```\n~~~\n## also not one\n~~~\n## Real too\n"
    assert headingshapes.headings(text) == [(1, "Real"), (8, "Real too")]


def test_headings_reads_a_block_that_prints_a_fence_of_its_own() -> None:
    text = "# Real\n````markdown\n```bash\n# not a heading\n```\n````\n## Real too\n"
    assert headingshapes.headings(text) == [(1, "Real"), (7, "Real too")]


@pytest.mark.parametrize(
    ("heading", "reason"),
    [
        ("Read [the rules](../AGENTS.md)", headingshapes.LINKED),
        ("The mark ![its bubble](../assets/logo.svg)", headingshapes.LINKED),
        ("Read [the rules][rules]", headingshapes.LINKED),
        ("Read [the rules]", headingshapes.LINKED),
        ("Read [the rules][]", headingshapes.LINKED),
        ("A note [with an aside] in it", headingshapes.LINKED),
        ("Press <kbd>Ctrl</kbd>+N", headingshapes.TAGGED),
        ("The site <https://example.com>", headingshapes.TAGGED),
        ("A closed heading ##", headingshapes.CLOSED),
        ("An _emphasised_ word", headingshapes.STRESSED),
        ("Risks &amp; notes", headingshapes.ENTITIED),
        ("Risks &#38; notes", headingshapes.ENTITIED),
        ("Risks &#x26; notes", headingshapes.ENTITIED),
    ],
)
def test_a_heading_this_rule_reads_too_literally_is_refused_by_name(
    heading: str, reason: str
) -> None:
    assert headingshapes.unsluggable(f"## {heading}\n") == [
        Unsluggable(line=1, heading=heading, reason=reason)
    ]


def test_a_setext_heading_is_refused_at_the_underline_that_makes_it_one() -> None:
    text = "Not a heading yet\n\nAn underlined heading\n=====================\n"
    assert headingshapes.unsluggable(text) == [
        Unsluggable(line=4, heading="An underlined heading", reason=headingshapes.UNDERLINED)
    ]


def test_a_setext_heading_underlined_with_dashes_is_refused_too() -> None:
    assert headingshapes.unsluggable("Underlined with one dash\n-\n") == [
        Unsluggable(line=2, heading="Underlined with one dash", reason=headingshapes.UNDERLINED)
    ]


def test_refusals_are_reported_in_line_order_however_they_were_found() -> None:
    text = "## Press <kbd>Esc</kbd>\n\nUnderlined\n---\n\n## An _emphasised_ word\n"
    assert [shape.line for shape in headingshapes.unsluggable(text)] == [1, 4, 6]


@pytest.mark.parametrize(
    "heading",
    [
        "Risks & notes",
        "hotkey → overlay → chat",
        "`Embedder` and its port",
        "The relaxation is a **leak**",
        "body/crates/os_* (per-platform OS backends)",
        "the loop context grows session_id",
        "brain/packages/body_client and cortex_core",
        "Setting a rule via edit_scheduled",
        "Writing it in C#",
        "`[not a link](nowhere.md)` as written",
        "Array index `a[0]`",
    ],
)
def test_a_heading_both_readings_agree_on_is_left_alone(heading: str) -> None:
    assert headingshapes.unsluggable(f"## {heading}\n") == []


@pytest.mark.parametrize(
    "text",
    [
        "Some prose.\n\n---\n",
        "- a list item\n---\n",
        "1. a numbered item\n---\n",
        "> a quotation\n---\n",
        "| a | table |\n---\n",
        "## an ATX heading\n---\n",
        "```\nnot prose\n---\n```\n",
        "```\nnot prose\n```\n---\n",
        "---\n",
    ],
)
def test_a_rule_that_underlines_nothing_is_not_a_setext_heading(text: str) -> None:
    assert headingshapes.unsluggable(text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "## Read [the rules](../AGENTS.md)\n",
            "docs/x.md:1: heading 'Read [the rules](../AGENTS.md)' brackets a span, which"
            " markdown may make a link and this rule always reads literally; quote the brackets"
            " in a code span, whose backticks this rule and a renderer both drop, or write the"
            " heading without them",
        ),
        (
            "## Array index a[0]\n",
            "docs/x.md:1: heading 'Array index a[0]' brackets a span, which markdown may make a"
            " link and this rule always reads literally; quote the brackets in a code span,"
            " whose backticks this rule and a renderer both drop, or write the heading"
            " without them",
        ),
        (
            "## Press <kbd>Ctrl</kbd>+N\n",
            "docs/x.md:1: heading 'Press <kbd>Ctrl</kbd>+N' contains angle-bracket markup, whose"
            " letters this rule keeps and a renderer drops; write it as plain text under leading"
            " hashes, so the source is what a renderer slugs",
        ),
        (
            "## A closed heading ##\n",
            "docs/x.md:1: heading 'A closed heading ##' is closed with hashes, which a renderer"
            " strips and this rule leaves as a trailing hyphen; write it as plain text under"
            " leading hashes, so the source is what a renderer slugs",
        ),
        (
            "## An _emphasised_ word\n",
            "docs/x.md:1: heading 'An _emphasised_ word' emphasises with underscores, a word"
            " character to this rule and a mark to a renderer; write it as plain text under"
            " leading hashes, so the source is what a renderer slugs",
        ),
        (
            "## Risks &amp; notes\n",
            "docs/x.md:1: heading 'Risks &amp; notes' contains an entity reference, whose letters"
            " this rule keeps and a renderer resolves; write it as plain text under leading"
            " hashes, so the source is what a renderer slugs",
        ),
        (
            "An underlined heading\n=====================\n",
            "docs/x.md:2: heading 'An underlined heading' is written as a setext underline, a"
            " heading shape this rule cannot see at all; write it as plain text under leading"
            " hashes, so the source is what a renderer slugs",
        ),
    ],
)
def test_problems_names_the_file_the_line_the_heading_and_the_remedy(
    text: str, expected: str
) -> None:
    assert headingshapes.problems("docs/x.md", text) == [expected]


def test_problems_says_nothing_about_a_document_written_plainly() -> None:
    assert headingshapes.problems("docs/x.md", "# Plain\n\n## Also plain\n") == []


def test_the_repo_itself_writes_no_heading_this_rule_cannot_slug() -> None:
    found = [
        problem
        for path in backloganchors.markdown_files(ROOT)
        for problem in headingshapes.problems(
            path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8", errors="replace")
        )
    ]
    assert found == []


def test_the_repo_really_offers_the_two_shapes_this_rule_must_not_report() -> None:
    quoted = 0
    underscored = 0
    for path in backloganchors.markdown_files(ROOT):
        text = path.read_text(encoding="utf-8", errors="replace")
        for _, heading in headingshapes.headings(text):
            quoted += "`" in heading
            underscored += bool(re.search(r"\w_\w", headingshapes.CODE_SPAN.sub("", heading)))
    assert quoted > 0
    assert underscored > 0
