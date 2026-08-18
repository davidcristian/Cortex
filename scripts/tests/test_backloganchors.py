"""Behaviour of the anchor half of the backlog link gate.

The path half of a link fails loudly when a file moves. The fragment half fails silently
when a heading stops being rendered, which is what a renamed area, an emptied one, and a
heading renamed in a decision record all do, so these tests are written around those
events rather than around the regexes.
"""

from pathlib import Path

import backloganchors
import backlogcheck
import headingshapes
from backloganchors import Index, Target

ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ── which links are the repo's own ─────────────────────────────────────────────


def test_local_targets_splits_a_relative_link_from_the_heading_it_aims_at() -> None:
    text = (
        "See [the sibling](002-a-slug.md) and [the decision](../adr/ADR-0001.md#decision-7),\n"
        "and [a heading here](#what-remains).\n"
        "Not [the site](https://example.com/x), nor [the plain one](http://example.com/y),\n"
        "nor [the author](mailto:someone@example.com), nor [an empty one](),\n"
        "nor [a bare hash](#), which points at neither a file nor a heading.\n"
    )
    assert backloganchors.local_targets(text) == [
        Target(line=1, path="002-a-slug.md", fragment=""),
        Target(line=1, path="../adr/ADR-0001.md", fragment="decision-7"),
        Target(line=2, path="", fragment="what-remains"),
    ]


def test_local_targets_numbers_a_link_whose_own_text_wraps_from_where_it_opens() -> None:
    """Prose here is wrapped by hand, so a link's brackets and its target straddle lines."""
    text = "Line one.\n\nSee [the decision\nas written](../adr/ADR-0001.md#decision-7).\n"
    assert backloganchors.local_targets(text) == [
        Target(line=3, path="../adr/ADR-0001.md", fragment="decision-7")
    ]


def test_local_links_keeps_the_relative_targets_and_drops_the_rest() -> None:
    """Only a relative target can rot on a move, so only those are worth resolving."""
    text = (
        "See [the sibling](002-a-slug.md) and [the decision](../adr/ADR-0001.md#decision-7).\n"
        "Not [the site](https://example.com/x), nor [the plain one](http://example.com/y),\n"
        "nor [a heading](#what-remains), nor [the author](mailto:someone@example.com).\n"
    )
    assert backloganchors.local_links(text) == ["002-a-slug.md", "../adr/ADR-0001.md"]


def test_local_links_finds_nothing_in_prose_that_links_nowhere() -> None:
    assert backloganchors.local_links("Plain prose, with brackets [but no target] in it.\n") == []


# ── the anchor a heading offers ────────────────────────────────────────────────


def test_slug_lowercases_drops_punctuation_and_hyphenates_the_spaces() -> None:
    assert backloganchors.slug("Actionable, once a seam or port changes (3)") == (
        "actionable-once-a-seam-or-port-changes-3"
    )
    assert (
        backloganchors.slug("The GPU sitting, start to finish") == "the-gpu-sitting-start-to-finish"
    )
    assert backloganchors.slug("body-overlay") == "body-overlay"
    assert (
        backloganchors.slug('Withdrawn: "the resident figure"') == "withdrawn-the-resident-figure"
    )


def test_slug_leaves_the_gap_a_dropped_symbol_stood_in_as_a_second_hyphen() -> None:
    """The renderer's rule, and the two shapes this repo's own headings really carry.

    Both spend a character between two spaces, and neither the renderer nor this collapses
    the pair of hyphens that leaves behind. Getting it wrong would strand every pointer at
    the fourteen headings here with an ampersand and the seven with an arrow.
    """
    assert backloganchors.slug("Risks & notes") == "risks--notes"
    assert backloganchors.slug("hotkey → overlay → chat") == "hotkey--overlay--chat"


def test_anchors_reads_every_heading_level_and_nothing_that_only_looks_like_one() -> None:
    text = (
        "# Deferred refinements\n\n"
        "###### Six deep\n"
        "####### Seven is not a heading\n"
        "#not a heading either\n"
        "Prose about # something.\n"
        "## What remains  \n"
    )
    assert backloganchors.anchors(text) == frozenset(
        {"deferred-refinements", "six-deep", "what-remains"}
    )


def test_anchors_ignores_a_hash_inside_a_fenced_block() -> None:
    """A shell comment in a runbook fence is not a heading, and would offer a false anchor."""
    text = "# Real\n\n```bash\n# start the stack\n```\n\n~~~\n## also not one\n~~~\n\n## Real too\n"
    assert backloganchors.anchors(text) == frozenset({"real", "real-too"})


def test_anchors_numbers_a_repeated_heading_from_its_second_occurrence() -> None:
    """The rule a renderer uses, so a fragment aimed at the second one is judged correctly."""
    text = "## memory\n## memory\n## memory\n"
    assert backloganchors.anchors(text) == frozenset({"memory", "memory-1", "memory-2"})


# ── which files the scan reads ─────────────────────────────────────────────────


def test_markdown_files_finds_the_prose_and_skips_the_vendored_trees(tmp_path: Path) -> None:
    _write(tmp_path, "docs/index.md", "# Index\n")
    _write(tmp_path, "AGENTS.md", "# Rules\n")
    _write(tmp_path, "scripts/gate.py", "x = 1\n")
    _write(tmp_path, "node_modules/pkg/README.md", "# Vendored\n")
    _write(tmp_path, "body/target/notes.md", "# Built\n")
    (tmp_path / "docs" / "a-directory.md").mkdir()
    found = [
        path.relative_to(tmp_path).as_posix() for path in backloganchors.markdown_files(tmp_path)
    ]
    assert found == ["AGENTS.md", "docs/index.md"]


# ── the gate itself ────────────────────────────────────────────────────────────


def _index(root: Path, text: str) -> dict[Path, Index]:
    """Write a backlog index holding ``text`` and return the map the check reads."""
    path = _write(root, "docs/refinements/index.md", text)
    return {
        path.resolve(): Index(
            name="docs/refinements/index.md", anchors=backloganchors.anchors(text)
        )
    }


def test_check_passes_a_pointer_at_a_heading_the_index_renders(tmp_path: Path) -> None:
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "See [the area](../refinements/index.md#memory).\n")
    assert backloganchors.check(tmp_path, indexes) == []


def test_check_reports_a_pointer_at_a_heading_the_index_stopped_rendering(tmp_path: Path) -> None:
    """The whole point: renaming an area leaves the link resolving and the anchor dead."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory-and-recall\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "See [the area](../refinements/index.md#memory).\n")
    assert backloganchors.check(tmp_path, indexes) == [
        "docs/adr/ADR-0008.md:1: pointer '../refinements/index.md#memory' aims at a heading "
        "docs/refinements/index.md does not render"
    ]


def test_check_judges_nothing_aimed_at_an_index_whose_rendering_is_unknown(tmp_path: Path) -> None:
    """A backlog too broken to render is still an index, so its stale file is never read."""
    _write(tmp_path, "docs/refinements/index.md", "# Deferred refinements\n\n### memory\n")
    indexes = {
        (tmp_path / "docs/refinements/index.md").resolve(): Index(
            name="docs/refinements/index.md", anchors=None
        )
    }
    _write(tmp_path, "docs/adr/ADR-0008.md", "See [the area](../refinements/index.md#gone).\n")
    assert backloganchors.check(tmp_path, indexes) == []


def test_check_reads_an_index_pointer_at_its_own_hand_written_half(tmp_path: Path) -> None:
    """An index links to its own sections, so a pointer with no path is aimed at that file."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n[how](#how-to-work-this-backlog)\n")
    assert backloganchors.check(tmp_path, indexes) == [
        "docs/refinements/index.md:3: pointer '#how-to-work-this-backlog' aims at a heading "
        "docs/refinements/index.md does not render"
    ]


def test_check_reports_a_fragment_aimed_at_a_heading_any_other_document_lacks(
    tmp_path: Path,
) -> None:
    """The widening: a heading renamed in a decision record strands its readers the same way."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "# Memory\n\n## Risks flagged for maintainer review\n")
    _write(
        tmp_path,
        "docs/refinements/tasks/001-a-task.md",
        "See [the decision](../../adr/ADR-0008.md#risks-flagged-for-user-review).\n",
    )
    assert backloganchors.check(tmp_path, indexes) == [
        "docs/refinements/tasks/001-a-task.md:1: pointer "
        "'../../adr/ADR-0008.md#risks-flagged-for-user-review' aims at a heading "
        "docs/adr/ADR-0008.md does not offer"
    ]


def test_check_passes_a_fragment_aimed_at_a_heading_another_document_carries(
    tmp_path: Path,
) -> None:
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "# Memory\n\n## Risks flagged for maintainer review\n")
    _write(
        tmp_path,
        "docs/refinements/tasks/001-a-task.md",
        "See [it](../../adr/ADR-0008.md#risks-flagged-for-maintainer-review).\n",
    )
    assert backloganchors.check(tmp_path, indexes) == []


def test_check_says_nothing_about_a_fragment_on_a_target_that_is_not_markdown(
    tmp_path: Path,
) -> None:
    """A line anchor addresses a file by number, a scheme with no headings to be wrong about."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "proto/body.proto", "service BrainService {}\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "See [the rpc](../../proto/body.proto#L42).\n")
    assert backloganchors.check(tmp_path, indexes) == []


def test_check_reports_a_fragment_aimed_at_markdown_the_scan_never_read(tmp_path: Path) -> None:
    """Fail closed: missing, outside the tree, or vendored all leave the question unanswered."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "node_modules/pkg/README.md", "# Vendored\n\n## Install\n")
    _write(
        tmp_path,
        "docs/adr/ADR-0008.md",
        "See [the gone one](moved-away.md#a-heading)\nand [the vendored one]"
        "(../../node_modules/pkg/README.md#install).\n",
    )
    assert backloganchors.check(tmp_path, indexes) == [
        f"docs/adr/ADR-0008.md:1: pointer 'moved-away.md#a-heading' {backloganchors.UNREAD}",
        "docs/adr/ADR-0008.md:2: pointer '../../node_modules/pkg/README.md#install' "
        f"{backloganchors.UNREAD}",
    ]


def test_check_reports_a_heading_whose_anchor_the_slug_rule_will_not_guess(
    tmp_path: Path,
) -> None:
    """The refusal reaches the gate: a shape this rule reads too literally is named where it is."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "# Memory\n\n## Press <kbd>Ctrl</kbd>+N\n")
    assert backloganchors.check(tmp_path, indexes) == [
        "docs/adr/ADR-0008.md:3: heading 'Press <kbd>Ctrl</kbd>+N' "
        f"{headingshapes.TAGGED}{headingshapes.PLAINLY}"
    ]


def test_check_judges_nothing_aimed_at_a_document_whose_headings_it_refused(
    tmp_path: Path,
) -> None:
    """Its anchor set is unknown, so saying it "does not offer" one would be an accusation.

    The same silence an index too broken to render gets, and for the same reason: the run is
    already failing on the heading, and a second problem about a pointer that may well be
    correct would send the reader after the wrong thing.
    """
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    _write(tmp_path, "docs/adr/ADR-0008.md", "# Memory\n\n## Press <kbd>Ctrl</kbd>+N\n")
    _write(
        tmp_path,
        "docs/refinements/tasks/001-a-task.md",
        "See [the shortcut](../../adr/ADR-0008.md#ctrln).\n",
    )
    problems = backloganchors.check(tmp_path, indexes)
    assert len(problems) == 1
    assert problems[0].startswith("docs/adr/ADR-0008.md:3: heading")


def test_check_reports_a_markdown_file_it_cannot_read(tmp_path: Path) -> None:
    """A scan that dies on one file reports nothing about the rest, so it reports the file."""
    indexes = _index(tmp_path, "# Deferred refinements\n\n### memory\n")
    (tmp_path / "docs" / "broken.md").write_bytes(b"# not \xff utf-8\n")
    problems = backloganchors.check(tmp_path, indexes)
    assert len(problems) == 1
    assert problems[0].startswith("docs/broken.md: cannot be read:")


# ── the real tree, since a rename lands here before it lands in a fixture ───────


def _repo_indexes() -> dict[Path, Index]:
    indexes: dict[Path, Index] = {}
    for kind, base, group_word in backlogcheck.BACKLOGS:
        _, offered = backlogcheck.run_one(ROOT, kind, base, group_word, write=False)
        assert offered is not None
        name = f"{base}/index.md"
        indexes[(ROOT / name).resolve()] = Index(name=name, anchors=offered)
    return indexes


def test_the_repo_itself_offers_every_anchor_aimed_at_it() -> None:
    assert backloganchors.check(ROOT, _repo_indexes()) == []


def test_the_repo_really_aims_pointers_at_both_indexes_from_outside_the_backlog() -> None:
    """A scan that matched nothing cannot fail, and the pointers most at risk are the far ones."""
    indexes = _repo_indexes()
    aimed: dict[Path, int] = dict.fromkeys(indexes, 0)
    for path in backloganchors.markdown_files(ROOT):
        if path.parent.name == "tasks" or path.name == "index.md":
            continue
        for target in backloganchors.local_targets(path.read_text(encoding="utf-8")):
            at = (path.parent / target.path).resolve()
            if target.fragment and at in aimed:
                aimed[at] += 1
    assert all(count > 0 for count in aimed.values()), aimed


def test_the_repo_really_aims_pointers_at_documents_that_are_not_a_backlog_index() -> None:
    """The same guard for the half this scan grew: judging nothing new would be a silent no-op."""
    indexes = _repo_indexes()
    elsewhere = 0
    for path in backloganchors.markdown_files(ROOT):
        for target in backloganchors.local_targets(path.read_text(encoding="utf-8")):
            at = (path.parent / target.path).resolve() if target.path else path.resolve()
            if target.fragment and at.suffix == backloganchors.MARKDOWN and at not in indexes:
                elsewhere += 1
    assert elsewhere > 0
