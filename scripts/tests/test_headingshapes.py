"""Behaviour of the heading shapes the anchor rule refuses to slug.

The gate next door slugs a heading's SOURCE text; a renderer slugs its RENDERED text. These
tests are written around that one disagreement: each refused shape is a heading where the two
readings differ, and each legal shape is one where they agree for a reason worth pinning, since
a rule that started reporting `Risks & notes` or `session_id` would redden a clean tree.
"""

import re
from pathlib import Path

import pytest

import backloganchors
import headingshapes
from headingshapes import Unsluggable

ROOT = Path(__file__).resolve().parents[2]


# ── which lines are headings at all ────────────────────────────────────────────


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
    """A runbook fence is full of shell comments, and none of them is a heading."""
    text = "# Real\n```bash\n# start the stack\n```\n~~~\n## also not one\n~~~\n## Real too\n"
    assert headingshapes.headings(text) == [(1, "Real"), (8, "Real too")]


# ── the six shapes this rule refuses ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("heading", "reason"),
    [
        # A renderer slugs the bracketed text alone, so this rule welds the target onto it.
        ("Read [the rules](../AGENTS.md)", headingshapes.LINKED),
        # An image is the same shape with a bang, and the same disagreement.
        ("The mark ![its bubble](../assets/logo.svg)", headingshapes.LINKED),
        # A reference link resolves elsewhere; the label is not part of the rendered text.
        ("Read [the rules][rules]", headingshapes.LINKED),
        # A renderer drops the tags; this rule keeps kbd and the slash as letters.
        ("Press <kbd>Ctrl</kbd>+N", headingshapes.TAGGED),
        # An autolink is angle brackets too, and its URL is not the rendered text either.
        ("The site <https://example.com>", headingshapes.TAGGED),
        # Markdown allows a closing run and a renderer strips it; here the space before it
        # survives as a trailing hyphen, so every pointer at the plain anchor is reported.
        ("A closed heading ##", headingshapes.CLOSED),
        # The underscore is a word character to this rule and a formatting mark to a renderer.
        ("An _emphasised_ word", headingshapes.STRESSED),
        # A named entity resolves to one character; this rule keeps its letters as text.
        ("Risks &amp; notes", headingshapes.ENTITIED),
        # A numeric entity is the same, in both of its spellings.
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
    """The loudest shape: `anchors()` cannot see it, so the document would offer nothing."""
    text = "Not a heading yet\n\nAn underlined heading\n=====================\n"
    assert headingshapes.unsluggable(text) == [
        Unsluggable(line=4, heading="An underlined heading", reason=headingshapes.UNDERLINED)
    ]


def test_a_setext_heading_underlined_with_dashes_is_refused_too() -> None:
    """A single dash under a paragraph line renders as a heading, so one is enough."""
    assert headingshapes.unsluggable("Underlined with one dash\n-\n") == [
        Unsluggable(line=2, heading="Underlined with one dash", reason=headingshapes.UNDERLINED)
    ]


def test_refusals_are_reported_in_line_order_however_they_were_found() -> None:
    """The inline shapes and the underlines are found in separate walks and merged."""
    text = "## Press <kbd>Esc</kbd>\n\nUnderlined\n---\n\n## An _emphasised_ word\n"
    assert [shape.line for shape in headingshapes.unsluggable(text)] == [1, 4, 6]


# ── what must stay legal, because the two readings agree ───────────────────────


@pytest.mark.parametrize(
    "heading",
    [
        # Both sides drop a character standing between two spaces and neither collapses the
        # pair of hyphens it leaves, which is why these two shapes already agree.
        "Risks & notes",
        "hotkey → overlay → chat",
        # A backtick and an asterisk are dropped by this rule and by a renderer alike, and
        # take no text with them, so 133 code-span headings and 4 starred ones are unaffected.
        "`Embedder` and its port",
        "The relaxation is a **leak**",
        "body/crates/os_* (per-platform OS backends)",
        # CommonMark never reads an underscore inside a word as emphasis, so both sides keep
        # it. Every underscore heading in this repo is of this kind.
        "the loop context grows session_id",
        "brain/packages/body_client and cortex_core",
        "Setting a rule via edit_scheduled",
        # A heading may end in a hash that is not a closing run: no whitespace precedes it.
        "Writing it in C#",
        # A link quoted inside a code span renders as its own literal text, so the backticks
        # come off on both sides and what is left disagrees about nothing.
        "`[not a link](nowhere.md)` as written",
    ],
)
def test_a_heading_both_readings_agree_on_is_left_alone(heading: str) -> None:
    assert headingshapes.unsluggable(f"## {heading}\n") == []


@pytest.mark.parametrize(
    "text",
    [
        # A rule after a blank line is a thematic break, which underlines nothing.
        "Some prose.\n\n---\n",
        # So is one under a line that opens a block of its own rather than paragraph text.
        "- a list item\n---\n",
        "1. a numbered item\n---\n",
        "> a quotation\n---\n",
        "| a | table |\n---\n",
        "## an ATX heading\n---\n",
        # And a rule inside a fence is somebody's shell output, not a heading.
        "```\nnot prose\n---\n```\n",
        # A fence closing right after prose leaves no predecessor for the rule below it.
        "```\nnot prose\n```\n---\n",
        # A rule at the very top of a file underlines nothing either.
        "---\n",
    ],
)
def test_a_rule_that_underlines_nothing_is_not_a_setext_heading(text: str) -> None:
    assert headingshapes.unsluggable(text) == []


# ── what the gate prints ───────────────────────────────────────────────────────


def test_problems_names_the_file_the_line_the_heading_and_the_remedy() -> None:
    text = "## Press <kbd>Ctrl</kbd>+N\n"
    assert headingshapes.problems("docs/x.md", text) == [
        "docs/x.md:1: heading 'Press <kbd>Ctrl</kbd>+N' "
        f"{headingshapes.TAGGED}{headingshapes.PLAINLY}"
    ]


def test_problems_says_nothing_about_a_document_written_plainly() -> None:
    assert headingshapes.problems("docs/x.md", "# Plain\n\n## Also plain\n") == []


# ── the real tree, since a heading lands here before it lands in a fixture ──────


def test_the_repo_itself_writes_no_heading_this_rule_cannot_slug() -> None:
    """The clean verdict is measured rather than assumed; it is what makes this a house style."""
    found = [
        problem
        for path in backloganchors.markdown_files(ROOT)
        for problem in headingshapes.problems(
            path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8", errors="replace")
        )
    ]
    assert found == []


def test_the_repo_really_offers_the_two_shapes_this_rule_must_not_report() -> None:
    """A refusal that matched nothing would be a rule nobody could tell from an absent one."""
    quoted = 0
    underscored = 0
    for path in backloganchors.markdown_files(ROOT):
        text = path.read_text(encoding="utf-8", errors="replace")
        for _, heading in headingshapes.headings(text):
            quoted += "`" in heading
            underscored += bool(re.search(r"\w_\w", headingshapes.CODE_SPAN.sub("", heading)))
    assert quoted > 0
    assert underscored > 0
