"""Off-peak download scheduler for SilverSpoon.

Pure logic + thin OS helpers, deliberately free of any PyQt import so it can be
unit-tested headlessly (see test_scheduler.py). The GUI owns the QTimer and the
task list; this module only decides *when* a window opens/closes and computes
the session summary. Windows-only bits (wake timer, keep-awake) degrade to
no-ops elsewhere.
"""
import datetime as dt
import json
import os
import socket
import subprocess
import sys

# Mon=0 .. Sun=6  (matches datetime.weekday())
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]

WAKE_TASK_NAME = "SilverSpoonOffPeak"


def default_schedule():
    """Additive default; an absent 'schedule' key means the feature is off."""
    return {
        "enabled": False,
        "start": "02:00",
        "end": "06:00",
        "recurrence": "weekly",       # "weekly" | "once"
        "days": [0, 1, 2, 3, 4, 5, 6],  # active weekdays for "weekly"
        "date": "",                    # YYYY-MM-DD for "once"
        "wake_timer": False,           # register a Windows wake task
        "keep_awake": True,            # block sleep while a window is open
    }


def parse_hhmm(value):
    h, m = str(value).split(":")
    return dt.time(int(h), int(m))


def split_12h(hhmm):
    """'HH:mm' (24h) -> (hour_1_12, minute, 'AM'|'PM'). 00:xx->12 AM, 12:xx->12 PM."""
    h, m = (int(x) for x in hhmm.split(":"))
    ampm = "AM" if h < 12 else "PM"
    return (h % 12 or 12), m, ampm


def join_24h(hour_12, minute, ampm):
    """(hour_1_12, minute, 'AM'|'PM') -> 'HH:mm' (24h)."""
    h = hour_12 % 12
    if ampm == "PM":
        h += 12
    return f"{h:02d}:{minute:02d}"


def _fmt_time(hhmm):
    """'HH:mm' (24h) -> '2:00 AM' style (no leading zero on the hour)."""
    h, m, ampm = split_12h(hhmm)
    return f"{h}:{m:02d} {ampm}"


def describe_schedule(sched):
    """One-line human summary of an armed schedule; '' when not enabled.

    Examples: 'Daily 2:00 AM-6:00 AM', 'Mon, Wed, Fri 11:00 PM-5:00 AM',
    'Once on 2026-08-25, 2:00 AM-6:00 AM'. Appends ' (N downloads)' when the
    schedule targets a specific non-empty list of downloads.
    """
    if not sched.get("enabled"):
        return ""
    window = f"{_fmt_time(sched['start'])}–{_fmt_time(sched['end'])}"
    if sched.get("recurrence") == "once":
        prefix = f"Once on {sched.get('date') or ''}, "
    else:
        days = sorted(set(sched["days"] if "days" in sched else range(7)))
        if len(days) == 7:
            prefix = "Daily "
        else:
            prefix = ", ".join(WEEKDAY_NAMES[d][:3] for d in days) + " "
    text = f"{prefix}{window}"
    targets = sched.get("targets")
    if isinstance(targets, list) and targets:
        text += f" ({len(targets)} downloads)"
    return text


def _day_active(start_date, sched):
    if sched.get("recurrence") == "once":
        return start_date.isoformat() == sched.get("date")
    # Distinguish "key absent" (legacy/partial settings -> default all days)
    # from "present but empty" (user unchecked every day -> never active).
    days = sched["days"] if "days" in sched else list(range(7))
    return start_date.weekday() in set(days)


def is_within_window(now, sched):
    """True if `now` (a datetime) falls inside an active off-peak window.

    Handles windows that cross midnight by testing both the window that could
    have started today and the one that started yesterday. Weekday/once rules
    are always evaluated against the window's *start* date, so the small-hours
    tail of a window keeps the identity of the day it began on.
    """
    if not sched.get("enabled"):
        return False
    start_t = parse_hhmm(sched["start"])
    end_t = parse_hhmm(sched["end"])
    for day_offset in (0, 1):
        start_date = (now - dt.timedelta(days=day_offset)).date()
        start_dt = dt.datetime.combine(start_date, start_t)
        end_dt = dt.datetime.combine(start_date, end_t)
        if end_t <= start_t:                 # crosses midnight -> ends next day
            # ponytail: start == end is treated as a full 24h window (not
            # zero-length); the dialog offers distinct start/end so this is a
            # deliberate "all day" interpretation, not an error.
            end_dt += dt.timedelta(days=1)
        if start_dt <= now < end_dt and _day_active(start_date, sched):
            return True
    return False


class OffPeakScheduler:
    """Edge detector over is_within_window; poll() returns 'open'/'close'/None.

    Starts 'inactive', so launching the app already inside a window fires a
    single 'open' on the first poll (the wake-and-download path).
    """

    def __init__(self, sched):
        self.sched = sched
        self._active = False

    def update(self, sched):
        self.sched = sched

    def cancel_open(self):
        """Undo an 'open' edge that couldn't be honoured (e.g. no connection),
        so the next poll still inside the window re-fires 'open' to retry."""
        self._active = False

    def poll(self, now):
        inside = is_within_window(now, self.sched)
        if inside and not self._active:
            self._active = True
            return "open"
        if not inside and self._active:
            self._active = False
            return "close"
        return None


class OffPeakSession:
    """Accounting for one open window: byte snapshot at open + speed samples."""

    def __init__(self, started_at):
        self.started_at = started_at
        self.snapshot = {}           # task_key -> downloaded_bytes at open
        self.completed_before = set()  # task_keys already done at open
        self.speed_samples = []      # global MB/s samples across the window

    def sample_speed(self, mbps):
        if mbps > 0:
            self.speed_samples.append(mbps)


def summarize(session, end_at, bytes_now, completed_now):
    """Compute the window's metrics from open->close deltas."""
    bytes_downloaded = 0
    for key, nb in bytes_now.items():
        bytes_downloaded += max(0, nb - session.snapshot.get(key, 0))
    files_completed = len(set(completed_now) - session.completed_before)
    duration_seconds = max(0.0, (end_at - session.started_at).total_seconds())
    peak = max(session.speed_samples) if session.speed_samples else 0.0
    mb = bytes_downloaded / (1024 * 1024)
    avg = (mb / duration_seconds) if duration_seconds > 0 else 0.0
    return {
        "started_at": session.started_at.isoformat(timespec="seconds"),
        "ended_at": end_at.isoformat(timespec="seconds"),
        "duration_seconds": duration_seconds,
        "bytes_downloaded": bytes_downloaded,
        "files_completed": files_completed,
        "avg_speed_mbps": avg,
        "peak_speed_mbps": peak,
    }


def append_report(summary, path):
    """Append one JSON-line record; best-effort (never raises to the caller)."""
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary) + "\n")
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# OS helpers — Windows-specific, no-op / graceful elsewhere.
# --------------------------------------------------------------------------
def check_connection(host="1.1.1.1", port=443, timeout=1.5):
    # ponytail: called synchronously from the GUI thread on window-open, so the
    # timeout is kept short (worst-case ~1.5s stall, only at a window boundary
    # every 30s poll while offline). Move off-thread if UI-freeze reports appear.
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ctypes SetThreadExecutionState flags
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_AWAYMODE_REQUIRED = 0x00000040


def prevent_sleep():
    """Keep the machine awake while downloading. No-op off Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(
            _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_AWAYMODE_REQUIRED)
        return True
    except Exception:
        return False


def allow_sleep():
    """Release the keep-awake lock. No-op off Windows."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        return True
    except Exception:
        return False


def _run_powershell(command):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _trigger_expr(sched):
    at = sched["start"]
    if sched.get("recurrence") == "once":
        date = sched.get("date") or dt.date.today().isoformat()
        return f"New-ScheduledTaskTrigger -Once -At '{date}T{at}:00'"
    days = sched.get("days") or list(range(7))
    if len(days) == 7:
        return f"New-ScheduledTaskTrigger -Daily -At {at}"
    names = ",".join(WEEKDAY_NAMES[d] for d in sorted(set(days)))
    return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {names} -At {at}"


def register_wake_task(sched, executable, arguments=""):
    """Register a per-user Windows task that WAKES the PC and launches the app
    at the window start. Returns (ok, message). No admin rights needed for a
    task that runs in the current user's context.
    """
    if sys.platform != "win32":
        return False, "Wake timer is Windows-only; using keep-awake instead."
    # Escape single quotes for PowerShell single-quoted string literals ('' = ').
    exe = executable.replace("'", "''")
    arg_part = f" -Argument '{arguments.replace(chr(39), chr(39) * 2)}'" if arguments else ""
    ps = (
        f"$a = New-ScheduledTaskAction -Execute '{exe}'{arg_part}; "
        f"$t = {_trigger_expr(sched)}; "
        f"$s = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries "
        f"-DontStopIfGoingOnBatteries; "
        f"Register-ScheduledTask -TaskName '{WAKE_TASK_NAME}' -Action $a "
        f"-Trigger $t -Settings $s -Force | Out-Null"
    )
    try:
        r = _run_powershell(ps)
        if r.returncode == 0:
            return True, "Wake timer registered."
        return False, (r.stderr or r.stdout or "Failed to register wake task.").strip()
    except Exception as e:
        return False, str(e)


def unregister_wake_task():
    if sys.platform != "win32":
        return True, ""
    ps = (f"Unregister-ScheduledTask -TaskName '{WAKE_TASK_NAME}' "
          f"-Confirm:$false -ErrorAction SilentlyContinue")
    try:
        _run_powershell(ps)
        return True, ""
    except Exception as e:
        return False, str(e)


def get_report_path():
    return os.path.expanduser("~/.silverspoon_offpeak_report.jsonl")
