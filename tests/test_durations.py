from datetime import timedelta
import pytest

from tabula.durations import format_duration, parse_duration, timer_display


@pytest.mark.parametrize(
    "delta,expected",
    (
        (timedelta(hours=72, minutes=3, milliseconds=500), "72h3m0.5s"),
        (timedelta(), "0"),
        (timedelta(microseconds=1), "1us"),
        (timedelta(milliseconds=1), "1ms"),
        (timedelta(seconds=1), "1s"),
        (timedelta(minutes=1), "1m"),
        (timedelta(hours=1), "1h"),
        (timedelta(hours=1, minutes=1), "1h1m"),
        (timedelta(hours=1, seconds=1), "1h1s"),
        (timedelta(minutes=1, seconds=1), "1m1s"),
        (timedelta(hours=1, milliseconds=250), "1h0.25s"),
        (timedelta(minutes=1, milliseconds=250), "1m0.25s"),
        (timedelta(hours=1, minutes=1, milliseconds=250), "1h1m0.25s"),
        (timedelta(hours=1, microseconds=500), "1h0.0005s"),
        (timedelta(milliseconds=1, microseconds=200), "1.2ms"),
        (timedelta(microseconds=-1), "-1us"),
        (timedelta(milliseconds=-1), "-1ms"),
        (timedelta(seconds=-1), "-1s"),
        (timedelta(minutes=-1), "-1m"),
        (timedelta(hours=-1), "-1h"),
        (-timedelta(hours=1, minutes=1), "-1h1m"),
        (-timedelta(hours=1, seconds=1), "-1h1s"),
        (-timedelta(minutes=1, seconds=1), "-1m1s"),
        (-timedelta(hours=1, milliseconds=250), "-1h0.25s"),
        (-timedelta(minutes=1, milliseconds=250), "-1m0.25s"),
        (-timedelta(hours=1, minutes=1, milliseconds=250), "-1h1m0.25s"),
        (-timedelta(hours=1, microseconds=500), "-1h0.0005s"),
    ),
)
def test_format_duration(delta: timedelta, expected: str):
    actual = format_duration(delta)
    assert actual == expected


@pytest.mark.parametrize(
    "duration,expected",
    (
        ("0", timedelta()),
        ("-0", timedelta()),
        ("+0", timedelta()),
        ("0h", timedelta()),
        ("0m", timedelta()),
        ("0s", timedelta()),
        ("1us", timedelta(microseconds=1)),
        ("1ms", timedelta(milliseconds=1)),
        ("1s", timedelta(seconds=1)),
        ("2m", timedelta(minutes=2)),
        ("3h", timedelta(hours=3)),
        ("2h3m4s", timedelta(hours=2, minutes=3, seconds=4)),
        ("3m4s5us", timedelta(minutes=3, seconds=4, microseconds=5)),
        ("2us3m4s5h", timedelta(hours=5, minutes=3, seconds=4, microseconds=2)),
        ("1.5ms", timedelta(milliseconds=1, microseconds=500)),
        ("1.5s", timedelta(seconds=1, milliseconds=500)),
        ("1.5m", timedelta(minutes=1, seconds=30)),
        ("1.5h", timedelta(hours=1, minutes=30)),
        ("0.429496s", timedelta(microseconds=429496)),
        ("-1us", timedelta(microseconds=-1)),
        ("-1ms", timedelta(milliseconds=-1)),
        ("-1s", timedelta(seconds=-1)),
        ("-2m", timedelta(minutes=-2)),
        ("-3h", timedelta(hours=-3)),
        ("-3h2m", -timedelta(hours=3, minutes=2)),
        ("-3h2s", -timedelta(hours=3, seconds=2)),
    ),
)
def test_parse_duration(duration: str, expected: timedelta):
    actual = parse_duration(duration)
    assert actual == expected


@pytest.mark.parametrize(
    "duration,msg",
    (
        ("", "Empty duration string"),
        ("0.0", "Invalid duration string; expected unit"),
        (".0", "Invalid duration string; expected leading digit"),
        (".", "Invalid duration string; expected leading digit"),
        ("0.", "Invalid duration string; expected unit"),
    ),
)
def test_parse_duration_invalid(duration: str, msg: str):
    with pytest.raises(ValueError) as excinfo:
        parse_duration(duration)
    e = excinfo.value
    assert e.args[0] == msg


@pytest.mark.parametrize(
    "delta,expected",
    (
        (timedelta(), "00:00"),
        (timedelta(microseconds=1), "00:00"),
        (timedelta(milliseconds=1), "00:00"),
        (parse_duration("1s"), "00:01"),
        (parse_duration("1m"), "01:00"),
        (parse_duration("1h"), "1:00:00"),
        (parse_duration("1h1m"), "1:01:00"),
        (parse_duration("1h1s"), "1:00:01"),
        (parse_duration("1m1s"), "01:01"),
        (parse_duration("15m0s"), "15:00"),
        (parse_duration("4m39s"), "04:39"),
    ),
)
def test_timer_display(delta: timedelta, expected: str):
    actual = timer_display(delta)
    assert actual == expected
