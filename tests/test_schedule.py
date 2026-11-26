from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[1] / "custom_components" / "aquarium" / "schedule.py"
_SPEC = importlib.util.spec_from_file_location("aquarium_schedule", _PATH)
schedule = importlib.util.module_from_spec(_SPEC)
sys.modules["aquarium_schedule"] = schedule
_SPEC.loader.exec_module(schedule)

MODES = ["Day", "Daybreak", "Night"]


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 26, hour, minute, tzinfo=timezone.utc)


def test_parses_and_sorts_lines():
    points = schedule.parse_schedule("20:00 off\n12:00 Day\n\n# comment\n19:00=daybreak", schedule.modes_parser(MODES))
    assert [(p.at, p.value) for p in points] == [
        (time(12, 0), "Day"),
        (time(19, 0), "Daybreak"),
        (time(20, 0), schedule.OFF),
    ]


def test_dimmable_values():
    points = schedule.parse_schedule("8:00 25%\n9.30 100\n21:00 0", schedule.dimmable_parser)
    assert [p.value for p in points] == [25, 100, schedule.OFF]
    assert schedule.format_schedule(points) == "08:00 25%\n09:30 100%\n21:00 off"


@pytest.mark.parametrize(
    ("text", "parser", "line"),
    [
        ("12:00 sunset", schedule.modes_parser(MODES), 1),
        ("12:00 on\n25:00 off", schedule.switch_parser, 2),
        ("12:00 on\n12:00 off", schedule.switch_parser, 2),
        ("noon on", schedule.switch_parser, 1),
        ("12:00 150%", schedule.dimmable_parser, 1),
        ("12:00 50%", schedule.switch_parser, 1),
    ],
)
def test_rejects_bad_lines(text, parser, line):
    with pytest.raises(schedule.ScheduleError) as err:
        schedule.parse_schedule(text, parser)
    assert err.value.line == line


def test_value_at_wraps_to_previous_day():
    points = schedule.parse_schedule("12:00 on\n20:00 off", schedule.switch_parser)
    assert schedule.value_at(points, at(7, 0)) == schedule.OFF
    assert schedule.value_at(points, at(12, 0)) == schedule.ON
    assert schedule.value_at(points, at(19, 59)) == schedule.ON
    assert schedule.value_at(points, at(23, 0)) == schedule.OFF
    assert schedule.value_at([], at(12, 0)) is None


def test_next_change():
    points = schedule.parse_schedule("12:00 on\n20:00 off", schedule.switch_parser)
    assert schedule.next_change(points, at(11, 0)) == (at(12, 0), schedule.ON)
    assert schedule.next_change(points, at(12, 0)) == (at(20, 0), schedule.OFF)
    when, value = schedule.next_change(points, at(21, 0))
    assert (when.day, when.hour, value) == (27, 12, schedule.ON)


def test_steps_to_mode():
    assert schedule.steps_to_mode(0, 1, 3) == 1
    assert schedule.steps_to_mode(1, 0, 3) == 2
    assert schedule.steps_to_mode(2, 2, 3) == 0
