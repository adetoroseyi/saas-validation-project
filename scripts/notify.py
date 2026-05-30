"""Send notification emails to the campaign owner.

Two modes:
  --digest   Email a summary of replies processed in the last N hours.
             Runs after every monitor_responses.py pass.
  --report   Email the latest weekly report markdown.
             Runs after generate_report.py.

Required env vars:
  SENDING_EMAIL        The Gmail address sending the notification
  GMAIL_APP_PASSWORD   Gmail App Password (same one used for cold send)
  NOTIFICATION_EMAIL   Where to deliver the notification (your personal inbox)
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from common import (
    REPORTS_DIR,
    RESPONSES_PATH,
    SENT_LOG_PATH,
    get_logger,
    load_json,
)

log = get_logger("notify")

SENDING_EMAIL      = os.getenv("SENDING_EMAIL", "sheyi@trysignalbench.com")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL") or SENDING_EMAIL
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def _send(subject: str, body: str) -> bool:
    if not GMAIL_APP_PASSWORD:
        log.error("GMAIL_APP_PASSWORD not set — cannot send notification")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["to"]      = NOTIFICATION_EMAIL
        msg["from"]    = f"Campaign Bot <{SENDING_EMAIL}>"
        msg["subject"] = subject
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.ehlo(); s.starttls()
            s.login(SENDING_EMAIL, GMAIL_APP_PASSWORD)
            s.send_message(msg)
        log.info("Notification sent to %s", NOTIFICATION_EMAIL)
        return True
    except Exception as exc:
        log.error("Notification failed: %s", exc)
        return False


def _infer_action(classification: str) -> str:
    return {
        "interested":      "auto-replied asking follow-up questions",
        "pricing_question":"auto-replied with pricing tiers",
        "not_interested":  "marked closed, sequence stopped",
        "unsubscribe":     "added to suppression list, sequence stopped",
        "question":        "auto-replied with context about the research",
        "auto_reply":      "ignored (out-of-office)",
    }.get(classification, "no action")


def send_digest(hours: int = 3) -> int:
    resp_data = load_json(RESPONSES_PATH) or {"metadata": {}, "responses": []}
    sent_data = load_json(SENT_LOG_PATH)  or {"metadata": {"total_sent": 0, "daily_counts": {}}}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    for r in resp_data.get("responses", []):
        try:
            received = datetime.fromisoformat(r.get("received_date", ""))
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            if received >= cutoff:
                recent.append(r)
        except (ValueError, TypeError):
            pass

    if not recent:
        log.info("No new replies in last %d hours — digest skipped", hours)
        return 0

    total_sent = sent_data["metadata"].get("total_sent", 0)
    all_responses = resp_data.get("responses", [])
    all_time_counts = Counter(r.get("classification") for r in all_responses)

    lines = [
        f"{'=' * 48}",
        f"Campaign digest — {len(recent)} new {'reply' if len(recent) == 1 else 'replies'}",
        f"Total emails sent: {total_sent}  |  Total replies: {len(all_responses)}",
        f"{'=' * 48}",
        "",
    ]

    for r in recent:
        cls = r.get("classification", "unknown")
        lines += [
            f"From:    {r.get('company_name', '')} — {r.get('email', '')}",
            f"Concept: {r.get('concept', '?')}  |  Classified: {cls}",
            f"Action:  {_infer_action(cls)}",
            f"Preview: {(r.get('summary', '') or '')[:200].replace(chr(10), ' ')}",
            "",
        ]

    lines += [
        "── All-time breakdown ──",
    ]
    for cls, count in sorted(all_time_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {cls:<20} {count}")

    subject = f"[Campaign] {len(recent)} new {'reply' if len(recent) == 1 else 'replies'} — action taken"
    _send(subject, "\n".join(lines))
    return len(recent)


def send_report() -> bool:
    reports = sorted(
        REPORTS_DIR.glob("week_*_report.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        log.warning("No reports found in %s", REPORTS_DIR)
        return False

    latest   = reports[0]
    body     = latest.read_text(encoding="utf-8")
    week_num = latest.stem.replace("week_", "").replace("_report", "")
    subject  = f"[Campaign] Week {week_num} validation report"
    return _send(subject, body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digest", action="store_true", help="Send reply digest")
    parser.add_argument("--report", action="store_true", help="Send latest weekly report")
    parser.add_argument("--hours", type=int, default=3,
                        help="Look-back window for digest (default: 3)")
    args = parser.parse_args()

    if args.digest:
        count = send_digest(hours=args.hours)
        log.info("Digest: %d new replies notified", count)
    elif args.report:
        ok = send_report()
        return 0 if ok else 1
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())