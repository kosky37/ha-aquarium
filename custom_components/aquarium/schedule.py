from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Union

OFF = "off"
ON = "on"

Value = Union[str, int]

_LINE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*[-=]?\s*(\S.*?)\s*$")
_PERCENT = re.compile(r"^(\d{1,3})\s*%?$")


class ScheduleError(ValueError):
    def __init__(self, line: int, text: str, reason: str) -> None:
        super().__init__(f"line {line}: {reason}")
        self.line = line
        self.text = text
        self.reason = reason


@dataclass(frozen=True)
class Point:
    at: time
    value: Value


def switch_parser(text: str) -> Value:
    low = text.strip().lower()
    if low in (OFF, "0"):
        return OFF
    if low in (ON, "1"):
        return ON
    raise ValueError("use on or off")


def dimmable_parser(text: str) -> Value:
    low = text.strip().lower()
    if low in (OFF, "0", "0%"):
        return OFF
    if low == ON:
        return ON
    match = _PERCENT.match(low)
    if match:
        level = int(match.group(1))
        if 1 <= level <= 100:
            return level
    raise ValueError("use off, on or a brightness from 1% to 100%")


def modes_parser(modes: Sequence[str]) -> Callable[[str], Value]:
    lookup = {mode.strip().lower(): mode for mode in modes}

    def parse(text: str) -> Value:
        low = text.strip().lower()
        if low == OFF:
            return OFF
        if low == ON:
            return ON
        if low in lookup:
            return lookup[low]
        raise ValueError("use off, on or one of: " + ", ".join(modes))

    return parse


def parse_schedule(text: str | None, parser: Callable[[str], Value]) -> list[Point]:
    points: list[Point] = []
    seen: set[time] = set()
    for number, raw in enumerate((text or "").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE.match(stripped)
        if not match:
            raise ScheduleError(number, raw, "expected a line like 08:30 on")
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise ScheduleError(number, raw, "time must be between 00:00 and 23:59")
        try:
            value = parser(match.group(3))
        except ValueError as err:
            raise ScheduleError(number, raw, str(err)) from err
        at = time(hour, minute)
        if at in seen:
            raise ScheduleError(number, raw, "this time is already used")
        seen.add(at)
        points.append(Point(at, value))
    points.sort(key=lambda point: point.at)
    return points


def format_schedule(points: Sequence[Point]) -> str:
    return "\n".join(f"{p.at.strftime('%H:%M')} {format_value(p.value)}" for p in points)


def format_value(value: Value) -> str:
    if isinstance(value, int):
        return f"{value}%"
    return str(value)


def value_at(points: Sequence[Point], now: datetime) -> Value | None:
    if not points:
        return None
    current = points[-1]
    moment = now.time()
    for point in points:
        if point.at <= moment:
            current = point
        else:
            break
    return current.value


def next_change(points: Sequence[Point], now: datetime) -> tuple[datetime, Value] | None:
    if not points:
        return None
    moment = now.time().replace(microsecond=0)
    for point in points:
        if point.at > moment:
            return _at(now, point.at, 0), point.value
    return _at(now, points[0].at, 1), points[0].value


def _at(now: datetime, at: time, days: int) -> datetime:
    day = now.date() + timedelta(days=days)
    return datetime.combine(day, at, tzinfo=now.tzinfo)


def steps_to_mode(current: int, target: int, count: int) -> int:
    return (target - current) % count
