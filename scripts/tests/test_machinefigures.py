import pytest

import machinefigures
from bannedwords import Hit


def _figures(*lines: str) -> list[Hit]:
    return machinefigures.find_figures(list(enumerate(lines, start=1)))


@pytest.mark.parametrize(
    ("text", "figure"),
    [
        ("drew about 40 W at idle", "40 W"),
        ("a 175W brick", "175W"),
        ("a 1.5 kW supply", "1.5 kW"),
        ("drew 120 watts", "120 watts"),
        ("one Watt more: 1 Watt", "1 Watt"),
        ("the SM clock read 2250 MHz", "2250 MHz"),
        ("boosts to 2.25 GHz", "2.25 GHz"),
        ("a 1,867mhz floor", "1,867mhz"),
        ("| load | memory clock, MHz |", "MHz"),
        ("in GHz.", "GHz"),
    ],
)
def test_a_figure_in_watts_or_a_clock_unit_is_found(text: str, figure: str) -> None:
    assert _figures(text) == [Hit(line=1, word=figure)]


@pytest.mark.parametrize(
    "text",
    [
        "24 GB of VRAM and 128 GB of RAM",
        "5600 MT/s",
        "a 32 C reading, 41 °C at load",
        "fan at 30 %",
        "the W3C name, U+FF3C and 0x31EB6C",
        "4 Ws and a 2 Watch",
        "an x86 W, the v1.5 W",
        "fooMHz and MHzBar",
        "a `2250 MHz` paste and [a link](https://example.com/40W)",
    ],
)
def test_other_figures_and_masked_text_are_not_found(text: str) -> None:
    assert _figures(text) == []


def test_a_figure_split_by_a_line_break_is_found_on_the_line_of_its_number() -> None:
    assert _figures("plain", "read 1770 to 2100", "MHz over the run") == [
        Hit(line=2, word="2100 MHz")
    ]


def test_every_figure_is_found_on_its_own_line() -> None:
    run = [(4, "a 150 W limit"), (5, "148 W of draw at 1927 MHz")]
    assert machinefigures.find_figures(run) == [
        Hit(line=4, word="150 W"),
        Hit(line=5, word="148 W"),
        Hit(line=5, word="1927 MHz"),
    ]
