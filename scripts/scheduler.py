"""Master scheduler for the SaaS validation system.

This script is the single entrypoint invoked by cron or GitHub Actions.
It looks at the current time and day-of-week and decides which other
scripts to run. The actual logic lives in source_leads.py, send_emails.py,
monitor_responses.py, and generate_report.py — this file only orchestrates.

Scheduling (all times in GMT):

    Mon-Fri 07:00   source_leads.py
    Mon-Fri 08:00   send_emails.py   (first wave — new leads)
    Mon-Fri 08:30   send_emails.py   (day-3 follow-ups)
    Mon-Fri 09:00   send_emails.py   (day-7 breakups)
    Mon-Fri 10:00   monitor_responses.py
    Mon-Fri 12:00   monitor_responses.py
    Mon-Fri 14:00   monitor_responses.py
    Mon-Fri 16:00   monitor_responses.py
    Mon-Fri 18:00   monitor_responses.py
    Sun     20:00   generate_report.py

Weekends: no sourcing, no sending. Only monitoring (low frequency).

Usage:
    python scripts/scheduler.py         # auto — picks task based on time
    python scripts/scheduler.py source  # force a specific task
    python scripts/scheduler.py send
    python scripts/scheduler.py monitor
    python scripts/scheduler.py report
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import get_logger

log = get_logger("scheduler")

SCRIPTS_DIR = Path(__file__).parent
PYTHON = sys.executable


def run(script: str, *args: str) -> int:
    cmd = [PYTHON, str(SCRIPTS_DIR / script), *args]
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    return result.returncode


def pick_task(now: datetime) -> str | None:
    weekday = now.weekday()  # 0 = Monday
    hour = now.hour
    minute = now.minute

    # Sunday report
    if weekday == 6 and hour == 20:
        return "report"

    # Weekdays only for sourcing and sending
    if weekday < 5:
        if hour == 7:
            return "source"
        if hour in (8, 9):
            return "send"
        if hour in (10, 12, 14, 16, 18):
            return "monitor"
    # Weekends — low-frequency monitoring only
    if weekday >= 5 and hour in (10, 16):
        return "monitor"
    return None


def main() -> int:
    if len(sys.argv) > 1:
        task = sys.argv[1]
    else:
        task = pick_task(datetime.now(timezone.utc))
        if task is None:
            log.info("No task scheduled for current time. Exiting.")
            return 0

    log.info("Selected task: %s", task)
    if task == "source":
        # Run all three lead sources in sequence. Each is independent —
        # if one fails the others still run.
        rc = 0
        rc |= run("source_leads.py")           # Google Maps + LinkedIn enrichment

        # Apollo — only if API key is configured
        import os as _os
        if _os.getenv("APOLLO_API_KEY"):
            rc |= run("source_apollo.py", "--limit", "50")
        else:
            log.info("APOLLO_API_KEY not set — skipping Apollo source")

        # Companies House (UK) — only if API key is configured
        if _os.getenv("COMPANIES_HOUSE_API_KEY"):
            rc |= run("source_companies_house.py", "--limit", "30")
            # Immediately enrich CH leads with Hunter emails (if key available)
            if _os.getenv("HUNTER_API_KEY"):
                rc |= run("source_hunter.py", "--limit", "25")
        else:
            log.info("COMPANIES_HOUSE_API_KEY not set — skipping Companies House source")

        return rc
    if task == "send":
        return run("send_emails.py")
    if task == "monitor":
        return run("monitor_responses.py", "--once")
    if task == "report":
        return run("generate_report.py")
    log.error("Unknown task: %s", task)
    return 2


if __name__ == "__main__":
    sys.exit(main())
