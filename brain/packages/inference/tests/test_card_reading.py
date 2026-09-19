from card_reading import (
    END,
    OFF_CARD,
    QUERY,
    START,
    CardReading,
    NoReadingError,
    reading_of,
    render,
    render_serving,
)

_ROW = "cortex (thinking-on, gpu, engine-budget)"
_FIELDS = (
    "clocks.sm=1500 clocks.max.sm=3000 power.draw=40.00 enforced.power.limit=140.00 "
    "power.max_limit=200.00 power.default_limit=100.00 clocks_event_reasons.sw_power_cap=Active"
)


def _read(stdout: str) -> CardReading:
    reading = reading_of(0, stdout, "")
    assert isinstance(reading, CardReading), reading
    return reading


def _refusal(returncode: int, stdout: str, stderr: str = "") -> str:
    reading = reading_of(returncode, stdout, stderr)
    assert isinstance(reading, NoReadingError), reading
    return str(reading)


def test_the_query_names_every_field_the_line_reads_without_header_or_units() -> None:
    assert QUERY == (
        "nvidia-smi",
        "--query-gpu=clocks.sm,clocks.max.sm,power.draw,enforced.power.limit,power.max_limit,"
        "power.default_limit,clocks_event_reasons.sw_power_cap",
        "--format=csv,noheader,nounits",
    )


def test_a_reading_renders_each_ratio_over_its_own_pair_and_then_every_field() -> None:
    reading = _read("1500, 3000, 40.00, 140.00, 200.00, 100.00, Active\n")
    assert render(START, _ROW, reading) == (
        f"  card reading at start of {_ROW}: ceiling 0.70 of max and 1.40 of default, "
        f"draw 0.20 of max, clock 0.50 of max, sw power cap Active; {_FIELDS}"
    )


def test_the_end_reading_is_named_as_the_end() -> None:
    reading = _read("1500, 3000, 40.00, 140.00, 200.00, 100.00, Active")
    assert render(END, _ROW, reading).startswith(f"  card reading at end of {_ROW}: ceiling 0.70")


def test_a_field_the_driver_does_not_report_leaves_only_its_own_ratios_unread() -> None:
    reading = _read("[N/A], 3000, 40.00, [N/A], 200.00, 100.00, Not Active")
    line = render(START, _ROW, reading)
    assert "ceiling n/a of max and n/a of default, draw 0.20 of max, clock n/a of max" in line
    assert "enforced.power.limit=[N/A]" in line


def test_a_zero_whole_is_unread_rather_than_divided() -> None:
    reading = _read("1500, 0, 40.00, 140.00, 200.00, 0.00, Not Active")
    assert reading.ratio("clocks.sm", "clocks.max.sm") == "n/a"
    assert reading.ratio("enforced.power.limit", "power.default_limit") == "n/a"
    assert reading.ratio("power.draw", "power.max_limit") == "0.20"


def test_a_failed_call_reports_its_exit_and_what_it_said_on_one_line() -> None:
    said = _refusal(127, "", 'OCI runtime exec failed:\n  exec: "nvidia-smi": not found\n')
    assert said == 'exit 127, OCI runtime exec failed: exec: "nvidia-smi": not found'
    assert _refusal(1, "", "") == "exit 1, no output"


def test_a_failed_call_that_printed_to_stdout_reports_that() -> None:
    assert _refusal(2, 'Field "clocks.gpu" is not a valid field to query.\n') == (
        'exit 2, Field "clocks.gpu" is not a valid field to query.'
    )


def test_anything_but_exactly_one_device_is_no_reading() -> None:
    one = "1500, 3000, 40.00, 140.00, 200.00, 100.00, Active"
    assert _refusal(0, f"{one}\n{one}\n") == "2 devices reported, where a row is served on one"
    assert _refusal(0, "\n") == "0 devices reported, where a row is served on one"


def test_a_row_with_the_wrong_number_of_values_is_no_reading() -> None:
    assert _refusal(0, "1500, 3000, 35.00\n") == "3 values for 7 fields, 1500, 3000, 35.00"


def test_a_row_without_a_reading_says_why_in_place_of_figures() -> None:
    line = render(END, _ROW, NoReadingError(OFF_CARD))
    assert line == f"  card reading at end of {_ROW}: none, the row is served on the cpu"


def test_the_serving_line_spreads_each_ratio_over_every_reading_that_reports_it() -> None:
    readings = [
        _read("1500, 3000, 150.00, 160.00, 200.00, 100.00, Active"),
        _read("1200, 3000, 150.00, 120.00, 200.00, 100.00, Active"),
        _read("2700, 3000, 40.00, 180.00, 200.00, 100.00, Not Active"),
        _read("[N/A], 3000, 150.00, [N/A], 200.00, 100.00, Active"),
    ]
    assert render_serving(_ROW, 5, readings) == (
        f"  card readings every 5 s while serving {_ROW}: 4 taken, 0 unread; "
        "ceiling of max lowest 0.60 median 0.80 highest 0.90; "
        "clock of max lowest 0.40 median 0.50 highest 0.90; sw power cap Active in 3 of 4"
    )


def test_the_median_of_an_even_count_is_the_mean_of_its_middle_pair() -> None:
    readings = [
        _read("1200, 3000, 40.00, 140.00, 200.00, 100.00, Not Active"),
        _read("1500, 3000, 40.00, 160.00, 200.00, 100.00, Not Active"),
    ]
    line = render_serving(_ROW, 5, readings)
    assert "ceiling of max lowest 0.70 median 0.75 highest 0.80" in line


def test_an_unread_sample_is_counted_and_left_out_of_every_spread() -> None:
    readings = [
        NoReadingError("no answer in 15 s"),
        _read("1500, 3000, 40.00, 140.00, 200.00, 100.00, Not Active"),
    ]
    line = render_serving(_ROW, 2.5, readings)
    assert line.startswith(f"  card readings every 2.5 s while serving {_ROW}: 2 taken, 1 unread;")
    assert "ceiling of max lowest 0.70 median 0.70 highest 0.70" in line
    assert line.endswith("sw power cap Active in 0 of 1")


def test_a_ratio_no_reading_reports_is_unread_while_the_others_still_spread() -> None:
    readings = [_read("[N/A], 3000, 40.00, 140.00, 200.00, 100.00, Active")]
    line = render_serving(_ROW, 5, readings)
    assert "ceiling of max lowest 0.70 median 0.70 highest 0.70; clock of max n/a;" in line


def test_a_row_with_no_reading_says_so_with_the_last_reason() -> None:
    readings = [NoReadingError("exit 1, no output"), NoReadingError("no answer in 15 s")]
    assert render_serving(_ROW, 5, readings) == (
        f"  card readings every 5 s while serving {_ROW}: 2 taken, none read, "
        "the last no answer in 15 s"
    )
    assert render_serving(_ROW, 5, []) == (
        f"  card readings every 5 s while serving {_ROW}: 0 taken, none read"
    )
