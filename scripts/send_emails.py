"""Send scheduled cold emails via Gmail API.

This script is responsible for:
1. Finding all leads that are due an email (Day 0, Day 3, or Day 7 send)
2. Rendering the right template for each lead's assigned concept
3. Sending through the Gmail API with appropriate throttling
4. Updating sent_log.json and the lead's state

It does NOT source leads and does NOT classify replies — those are
separate scripts so each can be tested and scheduled independently.

Gmail authentication:
    Uses Google OAuth 2.0 flow. First-time setup requires you to generate
    credentials.json from Google Cloud Console and run the flow once to
    produce token.json. See 00-setup/email_domain_guide.md for details.

    For the MCP-driven mode (running through Claude Code), set
    USE_GMAIL_MCP=1 and the Gmail MCP tools are called from the
    orchestrator instead — this script's render_message() is still used
    to produce the envelope, but send() is skipped.

Usage:
    python scripts/send_emails.py              # live send
    python scripts/send_emails.py --dry-run    # render only, no send
    python scripts/send_emails.py --limit 5    # max N emails this run
"""

from __future__ import annotations

import argparse
import base64
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from common import (
    CONCEPT_NAMES,
    LEADS_PATH,
    SENT_LOG_PATH,
    TEMPLATES_DIR,
    add_to_launch_list,
    get_logger,
    load_json,
    load_suppression_set,
    now_iso,
    push_to_emailoctopus,
    resolve_industry_peer,
    save_json,
    today_date,
)

log = get_logger("send_emails")

SENDING_EMAIL = os.getenv("SENDING_EMAIL", "sheyi@trysignalbench.com")
SENDING_NAME = os.getenv("SENDING_NAME", "Sheyi Olu")
DAILY_SEND_CAP = int(os.getenv("DAILY_SEND_CAP", "25"))
MIN_SECONDS_BETWEEN_SENDS = int(os.getenv("MIN_SECONDS_BETWEEN_SENDS", "90"))
USE_GMAIL_MCP = os.getenv("USE_GMAIL_MCP", "0") == "1"
USE_SMTP = os.getenv("USE_SMTP", "0") == "1"   # GitHub Actions mode

# Subject line variants per concept — v3 final (locked 2026-04-11)
# Lowercase, 3-7 words, internal-memo feel. No spam-risk words.
SUBJECTS = {
    "A": [
        "compliance gap",
        "a risk question",
        "audit prep at {company_name}",
    ],
    "B": [
        "question re: referral process",
        "how does {company_name} find new work",
        "lead tracking at {company_name}",
    ],
    "C": [
        "too many tabs?",
        "dashboard question",
        "how many tools are you running",
    ],
    "D": [
        "manual process question",
        "still doing this manually?",
        "how much time does {company_name} spend on repeat tasks",
    ],
}


def parse_template(concept: str) -> dict[str, str]:
    """Extract the three email bodies from the concept's sequence template file."""
    path = TEMPLATES_DIR / f"concept_{concept.lower()}_sequence.md"
    text = path.read_text(encoding="utf-8")
    # Grab the first three fenced code blocks after "## Email N"
    bodies: dict[str, str] = {}
    for email_num in ("1", "2", "3"):
        pattern = rf"## Email {email_num}.*?```\n(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            bodies[email_num] = match.group(1).rstrip()
        else:
            raise ValueError(f"Email {email_num} body missing from {path}")
    return bodies


def render(body: str, lead: dict[str, Any]) -> str:
    """Fill mustache-style template variables from lead data.

    Variables resolved:
        {{first_name}}      — lead's first name (fallback: "there")
        {{company_name}}    — lead's company (fallback: "your business")
        {{industry_peer}}   — segment-aware peer noun for Concept B
                              e.g. "agency owner", "IT consultant", "recruiter"
                              Resolved from lead.sic_code then lead.industry.
    """
    first_name = lead.get("first_name") or "there"
    company_name = lead.get("company_name") or "your business"
    industry_peer = resolve_industry_peer(lead)
    return (
        body.replace("{{first_name}}", first_name)
            .replace("{{company_name}}", company_name)
            .replace("{{industry_peer}}", industry_peer)
    )


def due_sends(leads: list[dict[str, Any]], suppressed: set[str]) -> list[tuple[dict, int]]:
    """Return [(lead, email_number)] for every lead that needs a send today.

    email_number is 1, 2, or 3.
    """
    queue: list[tuple[dict, int]] = []
    now = datetime.now(timezone.utc)

    for lead in leads:
        if lead["email"] in suppressed:
            continue
        if lead["status"] in ("closed_not_interested", "unsubscribed", "bounced", "responded"):
            continue
        if lead.get("response_status"):  # any reply means stop
            continue

        last = lead.get("last_email_date")
        sent = lead.get("emails_sent", 0)

        if sent == 0:
            queue.append((lead, 1))
            continue
        if sent >= 3:
            continue
        if not last:
            continue

        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

        if sent == 1 and now - last_dt >= timedelta(hours=72):
            queue.append((lead, 2))
        elif sent == 2 and now - last_dt >= timedelta(hours=168):
            queue.append((lead, 3))
    return queue


def pick_subject(concept: str, email_num: int, original_subject: str | None, lead: dict) -> str:
    if email_num == 1:
        variants = SUBJECTS[concept]
        # Deterministic rotation using the lead id so A/B tests are stable
        lead_seed = int(re.sub(r"[^0-9]", "", lead.get("id", "0")) or "0")
        template = variants[lead_seed % len(variants)]
        return template.format(**lead)
    # Follow-ups use Re: + original
    return f"Re: {original_subject}" if original_subject else "Re: Following up"


def build_mime(lead: dict, subject: str, body: str) -> MIMEText:
    mime = MIMEText(body, "plain", "utf-8")
    mime["to"] = lead["email"]
    mime["from"] = f"{SENDING_NAME} <{SENDING_EMAIL}>"
    mime["subject"] = subject
    return mime


def send_via_smtp(mime: MIMEText) -> str:
    """Send via Gmail SMTP using an App Password.

    Used in GitHub Actions (USE_SMTP=1). Requires GMAIL_APP_PASSWORD secret.
    To generate an App Password:
      Google Account → Security → 2-Step Verification → App Passwords
      → Select 'Mail' → copy the 16-character password.
    """
    import smtplib

    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not app_password:
        raise SystemExit(
            "GMAIL_APP_PASSWORD is not set. Add it as a GitHub secret or .env var."
        )
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDING_EMAIL, app_password)
        server.send_message(mime)
    return f"smtp-{now_iso()}"


def send_via_gmail_api(mime: MIMEText) -> str:
    """Send via google-api-python-client. Returns the Gmail message id.

    Requires credentials.json + token.json in the scripts/ directory.
    See 00-setup/email_domain_guide.md for the OAuth setup walkthrough.
    """
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        raise SystemExit(
            "google-api-python-client is not installed. Run:\n"
            "  pip install google-api-python-client google-auth google-auth-oauthlib"
        )

    token_path = Path(__file__).parent / "token.json"
    if not token_path.exists():
        raise SystemExit(
            f"Missing {token_path}. Run scripts/auth_gmail.py once to complete the OAuth flow."
        )

    creds = Credentials.from_authorized_user_file(
        str(token_path), ["https://www.googleapis.com/auth/gmail.send"]
    )
    service = build("gmail", "v1", credentials=creds)
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return result["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=DAILY_SEND_CAP)
    args = parser.parse_args()

    leads_data = load_json(LEADS_PATH)
    if not leads_data or not leads_data.get("leads"):
        log.info("No leads to process. Run source_leads.py first.")
        return 0

    suppressed = load_suppression_set()
    sent_log = load_json(SENT_LOG_PATH) or {
        "metadata": {"total_sent": 0, "daily_counts": {}, "last_send_timestamp": None},
        "sends": [],
    }

    today = today_date()
    sent_today = sent_log["metadata"].get("daily_counts", {}).get(today, 0)
    remaining_quota = max(0, args.limit - sent_today)
    if remaining_quota == 0:
        log.info("Daily send cap (%d) already reached for %s", args.limit, today)
        return 0

    queue = due_sends(leads_data["leads"], suppressed)
    log.info("%d emails due. Quota remaining today: %d", len(queue), remaining_quota)

    # Shuffle deterministically so we don't drain one concept first
    random.Random(today).shuffle(queue)
    queue = queue[:remaining_quota]

    # Cache parsed templates per concept
    bodies_by_concept: dict[str, dict[str, str]] = {}

    sends_this_run = 0
    for lead, email_num in queue:
        concept = lead["concept_assigned"]
        if concept not in bodies_by_concept:
            bodies_by_concept[concept] = parse_template(concept)
        raw_body = bodies_by_concept[concept][str(email_num)]
        body = render(raw_body, lead)

        # For follow-ups, find the original subject from sent_log
        original_subject = None
        if email_num > 1:
            for s in reversed(sent_log["sends"]):
                if s["lead_id"] == lead["id"] and s["email_number"] == 1:
                    original_subject = s["subject"]
                    break
        subject = pick_subject(concept, email_num, original_subject, lead)

        mime = build_mime(lead, subject, body)

        log.info(
            "[%s] Email %d → %s <%s> (%s)",
            concept,
            email_num,
            lead["first_name"],
            lead["email"],
            CONCEPT_NAMES[concept],
        )

        if args.dry_run:
            log.info("DRY-RUN subject: %s", subject)
            log.info("DRY-RUN body preview:\n%s\n---", body[:200])
            continue

        if USE_GMAIL_MCP:
            log.info("USE_GMAIL_MCP=1 — leaving actual send to the Claude MCP orchestrator")
            message_id = f"pending-mcp-{lead['id']}-{email_num}"
        elif USE_SMTP:
            message_id = send_via_smtp(mime)
        else:
            message_id = send_via_gmail_api(mime)

        # Update lead state
        lead["emails_sent"] = email_num
        lead["last_email_date"] = now_iso()
        if email_num == 1:
            lead["status"] = "contacted"
            # Save to local launch list
            add_to_launch_list(lead, CONCEPT_NAMES[concept])
            # Push to EmailOctopus (cloud launch list)
            push_to_emailoctopus(lead, CONCEPT_NAMES[concept])

        # Log the send
        sent_log["sends"].append(
            {
                "lead_id": lead["id"],
                "email": lead["email"],
                "concept": concept,
                "email_number": email_num,
                "subject": subject,
                "sent_at": now_iso(),
                "message_id": message_id,
            }
        )
        sent_log["metadata"]["total_sent"] = sent_log["metadata"].get("total_sent", 0) + 1
        sent_log["metadata"]["last_send_timestamp"] = now_iso()
        sent_log["metadata"].setdefault("daily_counts", {})
        sent_log["metadata"]["daily_counts"][today] = (
            sent_log["metadata"]["daily_counts"].get(today, 0) + 1
        )

        sends_this_run += 1

        # Persist after every send so a crash doesn't lose state
        save_json(LEADS_PATH, leads_data)
        save_json(SENT_LOG_PATH, sent_log)

        # Throttle
        if sends_this_run < len(queue):
            time.sleep(MIN_SECONDS_BETWEEN_SENDS)

    log.info("Done. Sent %d emails this run.", sends_this_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
