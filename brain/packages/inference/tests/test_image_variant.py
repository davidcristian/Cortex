import zlib
from typing import TYPE_CHECKING, Any, cast

from pixel_font import missing
from rendered_screens import (
    CORPUS_FRAME,
    CORPUS_PAYLOAD_SCALE,
    CORPUS_TYPE_SCALE,
    PROBES,
    RENDERINGS,
    Rendering,
    TypeScale,
    drawn,
)
from test_injection_defense_live import (
    ATTACKS,
    ENGINE_BUDGET,
    MODELS,
    RENDERED_FRAMES,
    SHIPPED_BUDGET,
    SQUARE,
    TYPE_SCALES,
    VISION_MODELS,
    FrameAxis,
    capture_result,
    frame_axis,
    image_messages,
    server_argv,
)
from test_injection_defense_live import test_injection_defense_over_pixels as _matrix_row
from test_injection_defense_live import test_the_laundering_rate_across_payload_sizes as _series_row
from test_injection_defense_live import test_the_laundering_rate_at_each_frame as _rate_row

from cortex_core import SECURITY_PREAMBLE, ImagePart

if TYPE_CHECKING:
    import pytest

_PNG = RENDERINGS[0].build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
_ASK = "what is on my screen?"
_MAGNIFIED = tuple(frame for frame in RENDERED_FRAMES if frame != CORPUS_FRAME)

_EVERY_RENDERING = (*RENDERINGS, *PROBES)


def test_every_payload_is_fully_drawable_by_the_font() -> None:
    holes = {
        attack.name: missing(drawn(attack.injection))
        for attack in ATTACKS
        if missing(drawn(attack.injection))
    }
    assert not holes, f"the font cannot draw these payload characters: {holes}"


def test_every_rendering_of_every_attack_is_a_png_of_the_frame_it_was_asked_for() -> None:
    for frame in RENDERED_FRAMES:
        for rendering in RENDERINGS:
            for attack in ATTACKS:
                png = rendering.build(attack.injection, frame, CORPUS_TYPE_SCALE)
                assert png.startswith(b"\x89PNG\r\n\x1a\n"), f"{rendering.name}/{attack.name}"
                header = frame.width.to_bytes(4, "big") + frame.height.to_bytes(4, "big")
                assert png[16:24] == header, f"{rendering.name}/{attack.name} at {frame.label}"


def test_the_corpus_is_byte_identical_when_rendered_twice() -> None:
    for rendering in _EVERY_RENDERING:
        first = rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
        assert first == rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE), (
            rendering.name
        )


def test_every_rendering_is_accepted_by_the_shipped_image_part() -> None:
    for frame in RENDERED_FRAMES:
        for rendering in RENDERINGS:
            png = rendering.build(ATTACKS[0].injection, frame, CORPUS_TYPE_SCALE)
            part = ImagePart(
                data=png, mime_type="image/png", width=frame.width, height=frame.height
            )
            assert part.data == png


def test_two_renderings_of_one_attack_differ() -> None:
    pictures = {
        rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
        for rendering in _EVERY_RENDERING
    }
    assert len(pictures) == len(_EVERY_RENDERING)


def test_the_probes_are_real_screens_of_the_corpus_frame_and_stand_outside_the_corpus() -> None:
    for rendering in PROBES:
        assert rendering not in RENDERINGS, rendering.name
        png = rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE)
        assert png.startswith(b"\x89PNG\r\n\x1a\n"), rendering.name
        header = CORPUS_FRAME.width.to_bytes(4, "big") + CORPUS_FRAME.height.to_bytes(4, "big")
        assert png[16:24] == header, rendering.name
        part = ImagePart(
            data=png,
            mime_type="image/png",
            width=CORPUS_FRAME.width,
            height=CORPUS_FRAME.height,
        )
        assert part.data == png, rendering.name


def test_the_square_is_the_two_corpus_corners_and_both_probes() -> None:
    assert SQUARE[: len(SQUARE) - len(PROBES)] == RENDERINGS[:2]
    assert SQUARE[len(SQUARE) - len(PROBES) :] == PROBES
    assert [rendering.name for rendering in SQUARE] == ["plain", "chrome", "bare", "advisory"]


def _rows(png: bytes, width: int) -> list[bytes]:
    """Return the RGB rows of a corpus PNG, unfiltered."""
    length = int.from_bytes(png[33:37], "big")
    raw = zlib.decompress(png[41 : 41 + length])
    stride = width * 3 + 1
    return [raw[line * stride + 1 : (line + 1) * stride] for line in range(len(raw) // stride)]


def test_a_magnified_render_is_the_same_picture_drawn_with_more_pixels() -> None:
    for rendering in RENDERINGS:
        small = _rows(
            rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE),
            CORPUS_FRAME.width,
        )
        assert len(small) == CORPUS_FRAME.height, rendering.name
        for frame in _MAGNIFIED:
            magnify = frame.magnify
            large = _rows(
                rendering.build(ATTACKS[0].injection, frame, CORPUS_TYPE_SCALE), frame.width
            )
            assert len(large) == frame.height, f"{rendering.name} at {frame.label}"
            for line in range(0, CORPUS_FRAME.height, 37):
                grown = b"".join(
                    small[line][x : x + 3] * magnify for x in range(0, CORPUS_FRAME.width * 3, 3)
                )
                for repeat in range(magnify):
                    assert large[line * magnify + repeat] == grown, (
                        f"{rendering.name} at {frame.label}:{line}"
                    )


def test_every_payload_size_the_series_runs_at_is_a_png_of_its_frame() -> None:
    for type_scale in TYPE_SCALES:
        for frame in RENDERED_FRAMES:
            for rendering in RENDERINGS:
                png = rendering.build(ATTACKS[0].injection, frame, type_scale)
                header = frame.width.to_bytes(4, "big") + frame.height.to_bytes(4, "big")
                assert png[16:24] == header, f"{rendering.name} at {type_scale.label}"


def test_a_payload_size_moves_nothing_above_the_payload() -> None:
    for rendering in _EVERY_RENDERING:
        corpus = _rows(
            rendering.build(ATTACKS[0].injection, CORPUS_FRAME, CORPUS_TYPE_SCALE),
            CORPUS_FRAME.width,
        )
        for type_scale in TYPE_SCALES[1:]:
            smaller = _rows(
                rendering.build(ATTACKS[0].injection, CORPUS_FRAME, type_scale), CORPUS_FRAME.width
            )
            moved = [line for line, row in enumerate(smaller) if row != corpus[line]]
            assert min(moved) == rendering.payload_top, (
                f"{rendering.name} at {type_scale.label}: the first row this size changes is "
                f"{min(moved)} and the rendering declares {rendering.payload_top}"
            )


def _painted(rendering: Rendering, type_scale: TypeScale) -> list[tuple[int, int]]:
    """The pixels of a screen the injected instruction paints at this size, as row and column."""
    blank = _rows(rendering.build("", CORPUS_FRAME, type_scale), CORPUS_FRAME.width)
    drawn_screen = _rows(
        rendering.build(ATTACKS[0].injection, CORPUS_FRAME, type_scale), CORPUS_FRAME.width
    )
    return [
        (line, x // 3)
        for line, (row, other) in enumerate(zip(blank, drawn_screen, strict=True))
        for x in range(0, len(row), 3)
        if row[x : x + 3] != other[x : x + 3]
    ]


def test_a_smaller_payload_is_set_in_the_same_column_of_pixels() -> None:
    for corpus_columns in (12, 24, 42, 48, 68):
        for type_scale in TYPE_SCALES:
            assert (
                type_scale.columns(corpus_columns) * type_scale.scale
                == corpus_columns * CORPUS_PAYLOAD_SCALE
            ), f"{corpus_columns} at {type_scale.label}"


def test_the_pitch_between_a_payloads_lines_follows_its_glyphs() -> None:
    for corpus_leading in (18, 40, 42, 46):
        for type_scale in TYPE_SCALES:
            drift = abs(
                type_scale.leading(corpus_leading) * CORPUS_PAYLOAD_SCALE
                - corpus_leading * type_scale.scale
            )
            assert drift < CORPUS_PAYLOAD_SCALE, f"{corpus_leading} at {type_scale.label}"


def test_a_smaller_payload_size_paints_a_smaller_share_of_the_screen() -> None:
    for rendering in _EVERY_RENDERING:
        painted = [len(_painted(rendering, type_scale)) for type_scale in TYPE_SCALES]
        assert all(count > 0 for count in painted), f"{rendering.name}: {painted}"
        assert painted == sorted(painted, reverse=True), f"{rendering.name}: {painted}"
        assert len(set(painted)) == len(painted), f"{rendering.name}: {painted}"


async def test_the_stand_in_text_names_the_frame_the_picture_really_arrived_at() -> None:
    for frame in RENDERED_FRAMES:
        png = RENDERINGS[0].build(ATTACKS[0].injection, frame, CORPUS_TYPE_SCALE)
        result = await capture_result(png, frame)
        assert frame.label in result.content, frame.label
        assert f"{frame.source_width}x{frame.source_height}" in result.content, frame.label
        assert frame.source_width * CORPUS_FRAME.width == CORPUS_FRAME.source_width * frame.width
        assert (
            frame.source_height * CORPUS_FRAME.height == CORPUS_FRAME.source_height * frame.height
        )


def test_the_variant_starts_its_server_with_the_deployments_own_image_budget() -> None:
    for model in VISION_MODELS:
        argv = server_argv(model, SHIPPED_BUDGET)
        assert argv[-4:] == (
            "--image-max-tokens",
            str(SHIPPED_BUDGET.image_max_tokens),
            "--ubatch-size",
            str(SHIPPED_BUDGET.image_max_tokens),
        ), model.label
        assert "--mmproj" in argv, model.label


def test_the_engine_budget_row_starts_with_neither_flag() -> None:
    for model in VISION_MODELS:
        argv = server_argv(model, ENGINE_BUDGET)
        assert "--image-max-tokens" not in argv, model.label
        assert "--ubatch-size" not in argv, model.label


def test_a_text_only_row_is_started_without_the_image_budget_pair() -> None:
    for model in MODELS:
        if model.mmproj is None:
            assert server_argv(model, SHIPPED_BUDGET) == server_argv(model, ENGINE_BUDGET)
            assert "--ubatch-size" not in server_argv(model, SHIPPED_BUDGET), model.label


def _costs(spent: tuple[int, int, int]) -> dict[str, int]:
    """One cost row, as the live row builds it: a frame label per delivered frame."""
    return dict(zip((frame.label for frame in RENDERED_FRAMES), spent, strict=True))


# What one corpus screen cost in image tokens at each frame, per candidate and per budget. They
# are dated readings rather than a contract, and they are here because the sort is what the live
# row's only assertion rests on.
_PUBLISHED_COSTS: tuple[tuple[str, tuple[int, int, int], FrameAxis], ...] = (
    ("the pick at the shipped budget", (629, 1010, 1010), FrameAxis.MORE_PICTURE),
    ("the pick at the engine's own budget", (266, 266, 266), FrameAxis.ONE_PICTURE),
    ("the alt at the shipped budget", (1010, 1010, 1010), FrameAxis.ONE_PICTURE),
    ("the alt at the engine's own budget", (1402, 4082, 4082), FrameAxis.MORE_PICTURE),
)


def test_every_published_cost_row_reads_as_one_of_the_two_frame_axes() -> None:
    for label, spent, axis in _PUBLISHED_COSTS:
        assert frame_axis(_costs(spent)) is axis, label


def test_a_row_whose_larger_frames_disagree_falls_in_neither_frame_axis() -> None:
    assert frame_axis(_costs((629, 629, 1010))) is None
    assert frame_axis(_costs((629, 1010, 629))) is None
    assert frame_axis(_costs((1010, 629, 629))) is None


def _axes(row: object) -> dict[object, tuple[object, ...]]:
    """The parametrize marks on one row, as each axis's name to the values it runs over."""
    marks = cast("list[pytest.Mark]", getattr(row, "pytestmark", []))
    return {mark.args[0]: tuple(mark.args[1]) for mark in marks if mark.name == "parametrize"}


def test_the_series_and_the_rate_run_in_every_row_the_matrix_runs_in() -> None:
    axes = _axes(_matrix_row)
    assert set(axes) == {"model", "frame", "budget"}
    assert _axes(_series_row) == axes
    assert _axes(_rate_row) == axes


def _tool_parts(wire: list[dict[str, object]]) -> list[dict[str, Any]]:
    """Return the content-parts array of the tool message closing a vision conversation."""
    parts = wire[-1]["content"]
    assert isinstance(parts, list)
    return cast("list[dict[str, Any]]", parts)


async def test_the_screen_reaches_the_wire_as_a_png_data_uri() -> None:
    result = await capture_result(_PNG)
    for framed in (True, False):
        parts = _tool_parts(image_messages(result, framed=framed, ask=_ASK))
        images = [part for part in parts if part["type"] == "image_url"]
        assert len(images) == 1, framed
        assert str(images[0]["image_url"]["url"]).startswith("data:image/png;base64,"), framed


async def test_the_two_variants_differ_by_the_defence_and_by_nothing_else() -> None:
    result = await capture_result(_PNG)
    framed = image_messages(result, framed=True, ask=_ASK)
    control = image_messages(result, framed=False, ask=_ASK)
    assert framed[0] == {"role": "system", "content": SECURITY_PREAMBLE}
    assert framed[1:3] == control[0:2]
    framed_parts, control_parts = _tool_parts(framed), _tool_parts(control)
    assert framed_parts[1:] == control_parts[1:]
    assert framed_parts[0] != control_parts[0]
    assert str(control_parts[0]["text"]) in str(framed_parts[0]["text"])
