"""Headless unit checks for the off-peak scheduler pure logic.

No GUI, no network, no third-party deps. Run with:  python test_scheduler.py
Every non-trivial branch of scheduler.py (window math, edge detection,
summary metrics) is pinned here so a regression fails loudly.
"""
import datetime as dt

import scheduler as sc


def D(y=2026, m=8, d=20, hh=0, mm=0, wd=None):
    """Build a datetime; if wd given, roll to the next date with that weekday."""
    base = dt.datetime(y, m, d, hh, mm)
    if wd is not None:
        base += dt.timedelta(days=(wd - base.weekday()) % 7)
    return base


# ---- is_within_window: same-day window -------------------------------------
def test_same_day_window():
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7))}
    assert sc.is_within_window(D(hh=3), s) is True
    assert sc.is_within_window(D(hh=1), s) is False
    assert sc.is_within_window(D(hh=6), s) is False   # end is exclusive
    assert sc.is_within_window(D(hh=2), s) is True    # start is inclusive


# ---- is_within_window: crosses midnight ------------------------------------
def test_midnight_crossing():
    s = {"enabled": True, "start": "23:00", "end": "05:00",
         "recurrence": "weekly", "days": list(range(7))}
    assert sc.is_within_window(D(hh=23, mm=30), s) is True   # before midnight
    assert sc.is_within_window(D(hh=2), s) is True           # after midnight
    assert sc.is_within_window(D(hh=12), s) is False


# ---- weekday filter --------------------------------------------------------
def test_weekday_filter():
    # active only Mon(0) and Tue(1)
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": [0, 1]}
    assert sc.is_within_window(D(hh=3, wd=0), s) is True     # Monday
    assert sc.is_within_window(D(hh=3, wd=2), s) is False    # Wednesday


def test_weekday_filter_midnight_uses_start_day():
    # Window 23:00->05:00 active only Fri(4). The 02:00 slice belongs to the
    # Friday window even though 'now' is Saturday.
    s = {"enabled": True, "start": "23:00", "end": "05:00",
         "recurrence": "weekly", "days": [4]}
    assert sc.is_within_window(D(hh=23, wd=4), s) is True    # Fri 23:00
    assert sc.is_within_window(D(hh=2, wd=5), s) is True     # Sat 02:00 == Fri window
    assert sc.is_within_window(D(hh=2, wd=6), s) is False    # Sun 02:00, no window


# ---- one-off schedule ------------------------------------------------------
def test_once_schedule():
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "once", "date": "2026-08-21"}
    assert sc.is_within_window(dt.datetime(2026, 8, 21, 3, 0), s) is True
    assert sc.is_within_window(dt.datetime(2026, 8, 22, 3, 0), s) is False


def test_12h_24h_roundtrip():
    for hhmm in ["00:00", "00:30", "02:00", "11:59", "12:00",
                 "12:45", "13:05", "23:59"]:
        h12, m, ap = sc.split_12h(hhmm)
        assert sc.join_24h(h12, m, ap) == hhmm, hhmm
    # the two easy-to-get-wrong noon/midnight cases
    assert sc.split_12h("00:15") == (12, 15, "AM")
    assert sc.split_12h("12:15") == (12, 15, "PM")


def test_disabled_never_matches():
    s = {"enabled": False, "start": "00:00", "end": "23:59",
         "recurrence": "weekly", "days": list(range(7))}
    assert sc.is_within_window(D(hh=12), s) is False


def test_empty_days_never_active():
    # Unchecking every weekday must mean "never", not silently "every day".
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": []}
    assert sc.is_within_window(D(hh=3, wd=0), s) is False
    assert sc.is_within_window(D(hh=3, wd=3), s) is False


def test_missing_days_key_defaults_all():
    # Legacy/partial settings with no 'days' key default to every day.
    s = {"enabled": True, "start": "02:00", "end": "06:00", "recurrence": "weekly"}
    assert sc.is_within_window(D(hh=3, wd=0), s) is True


# ---- edge detection --------------------------------------------------------
def test_scheduler_edges():
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7))}
    sch = sc.OffPeakScheduler(s)
    assert sch.poll(D(hh=1)) is None            # outside, no edge
    assert sch.poll(D(hh=3)) == "open"          # rising edge
    assert sch.poll(D(hh=4)) is None            # still inside, no repeat
    assert sch.poll(D(hh=7)) == "close"         # falling edge
    assert sch.poll(D(hh=8)) is None            # outside again


def test_cancel_open_refires_next_poll():
    # Simulates "opened but no connection": cancel_open() must let the next
    # in-window poll re-fire "open" so the retry path works.
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7))}
    sch = sc.OffPeakScheduler(s)
    assert sch.poll(D(hh=3)) == "open"
    sch.cancel_open()
    assert sch.poll(D(hh=3, mm=30)) == "open"   # re-fires instead of None


def test_scheduler_autostart_on_launch_inside_window():
    # App launched already inside the window -> first poll must fire "open".
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7))}
    sch = sc.OffPeakScheduler(s)
    assert sch.poll(D(hh=3)) == "open"


# ---- summary metrics -------------------------------------------------------
def test_summary_metrics():
    session = sc.OffPeakSession(started_at=dt.datetime(2026, 8, 20, 2, 0))
    session.snapshot = {"a": 0, "b": 1_000_000}          # bytes at open
    session.completed_before = {"b"}
    # speed samples in MB/s taken across the window
    session.speed_samples = [10.0, 20.0, 30.0]
    now_bytes = {"a": 500_000_000, "b": 1_500_000_000}   # a fresh, b resumed
    now_completed = {"a", "b"}                            # a newly done
    summ = sc.summarize(
        session, end_at=dt.datetime(2026, 8, 20, 4, 0),
        bytes_now=now_bytes, completed_now=now_completed)
    # bytes downloaded during window = (500M-0) + (1500M-1M)
    assert summ["bytes_downloaded"] == 500_000_000 + 1_499_000_000
    assert summ["files_completed"] == 1                  # only 'a' newly completed
    assert summ["duration_seconds"] == 2 * 3600
    assert abs(summ["peak_speed_mbps"] - 30.0) < 1e-9
    # avg = total_bytes / duration, expressed MB/s
    expected_avg = (summ["bytes_downloaded"] / (1024 * 1024)) / (2 * 3600)
    assert abs(summ["avg_speed_mbps"] - expected_avg) < 1e-6


# ---- describe_schedule -----------------------------------------------------
def test_describe_disabled_is_empty():
    s = {"enabled": False, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7))}
    assert sc.describe_schedule(s) == ""


def test_describe_daily():
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7))}
    assert sc.describe_schedule(s) == "Daily 2:00 AM–6:00 AM"


def test_describe_specific_days():
    s = {"enabled": True, "start": "23:00", "end": "05:00",
         "recurrence": "weekly", "days": [0, 2, 4]}
    assert sc.describe_schedule(s) == "Mon, Wed, Fri 11:00 PM–5:00 AM"


def test_describe_once():
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "once", "date": "2026-08-25"}
    assert sc.describe_schedule(s) == "Once on 2026-08-25, 2:00 AM–6:00 AM"


def test_describe_targets_suffix():
    s = {"enabled": True, "start": "02:00", "end": "06:00",
         "recurrence": "weekly", "days": list(range(7)),
         "targets": ["a", "b", "c"]}
    assert sc.describe_schedule(s) == "Daily 2:00 AM–6:00 AM (3 downloads)"
    # None / empty targets add no suffix
    s["targets"] = None
    assert sc.describe_schedule(s) == "Daily 2:00 AM–6:00 AM"
    s["targets"] = []
    assert sc.describe_schedule(s) == "Daily 2:00 AM–6:00 AM"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} passed")
