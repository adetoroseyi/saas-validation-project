"""Poll Gmail for replies to outreach sends, classify them, and log.

Runs every 2 hours during business hours. Reads the Gmail inbox for
unread messages from any address matching a lead in leads.json, classifies
the reply into one of six categories, updates responses.json and the
lead's state, and — where appropriate — drafts a reply using the
templates in 04-responses/auto_replies/reply_templates.md.

CRITICAL: Auto-replies are created as DRAFTS only. A human (or the
Claude orchestrator in a supervised session) reviews and sends them.
This script never sends unsupervised replies because the classification
layer can be fooled by prompt injection in the inbound email body.

Usage:
    python scripts/monitor_responses.py
    python scripts/monitor_responses.py --once       # single poll
    python scripts/monitor_responses.py --classify-only

Gmail auth: same credentials.json / token.json as send_emails.py.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any

from common import (
    CONCEPT_NAMES,
    CONCEPT_PRICES,
    LEADS_PATH,
    RESPONSES_PATH,
    add_to_suppression,
    get_logger,
    load_json,
    normalise_email,
    now_iso,
    save_json,
    update_emailoctopus_tag,
    update_launch_list_response,
)

log = get_logger("monitor_responses")

# --- Classification rules -----------------------------------------------
# Regex-based first pass. Anything ambiguous falls through to "question"
# and is queued for manual or LLM classification.

UNSUBSCRIBE_RE = re.compile(
    r"\b(unsubscribe|opt[-\s]?out|remove me|stop emailing|take me off|"
    r"do not (contact|email)|please stop)\b",
    re.IGNORECASE,
)
STOP_ALONE_RE = re.compile(r"^\s*stop\s*\.?\s*$", re.IGNORECASE | re.MULTILINE)

AUTO_REPLY_RE = re.compile(
    r"\b(out of office|ooo|on leave|on holiday|on vacation|"
    r"automatic reply|auto[-\s]?reply|currently away|"
    r"will be back on|return(ing)? to the office)\b",
    re.IGNORECASE,
)

PRICING_RE = re.compile(
    r"\b(how much|price|pricing|cost|costs|fee|fees|budget|"
    r"what would .* charge|\$|£|€)\b",
    re.IGNORECASE,
)

NOT_INTERESTED_RE = re.compile(
    r"\b(not interested|no thanks|not for us|doesn['\u2019]?t apply|"
    r"we (already have|have one|use)|not a (priority|fit)|pass|"
    r"nothing to discuss)\b",
    re.IGNORECASE,
)

INTERESTED_RE = re.compile(
    r"\b(interesting|curious|tell me more|sounds (good|great|like)|"
    r"happy to chat|would love to|would be keen|keen to|could help|"
    r"we struggle with|painful|frustrating|waste of time|eats time)\b",
    re.IGNORECASE,
)

QUESTION_RE = re.compile(
    r"(\?|who are you|what('?s| is) this|what do you do|tell me more)",
    re.IGNORECASE,
)


def classify(body: str) -> str:
    """Return one of: unsubscribe, auto_reply, pricing_question, not_interested,
    interested, question."""
    text = body or ""

    if STOP_ALONE_RE.search(text) or UNSUBSCRIBE_RE.search(text):
        return "unsubscribe"
    if AUTO_REPLY_RE.search(text):
        return "auto_reply"
    if PRICING_RE.search(text):
        return "pricing_question"
    if INTERESTED_RE.search(text):
        return "interested"
    if NOT_INTERESTED_RE.search(text):
        return "not_interested"
    if QUESTION_RE.search(text):
        return "question"
    return "question"  # default to safest category (human review)


# --- Lead lookup --------------------------------------------------------


def find_lead_by_email(leads: list[dict[str, Any]], email: str) -> dict[str, Any] | None:
    email = normalise_email(email)
    for lead in leads:
        if normalise_email(lead["email"]) == email:
            return lead
    return None


# --- Gmail integration (requires google-api-python-client) --------------


def get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        raise SystemExit(
            "google-api-python-client not installed. See send_emails.py for setup."
        )
    from pathlib import Path as _P

    token_path = _P(__file__).parent / "token.json"
    creds = Credentials.from_authorized_user_file(
        str(token_path),
        [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
        ],
    )
    return build("gmail", "v1", credentials=creds)


def fetch_unread_replies(service, known_senders: set[str]) -> list[dict[str, Any]]:
    """Return a list of {sender, subject, body, thread_id, message_id} for unread
    inbox messages whose From address matches a known lead."""
    results = service.users().messages().list(userId="me", q="is:unread in:inbox").execute()
    messages = results.get("messages", [])
    replies = []
    for m in messages:
        full = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        from_addr = extract_email(headers.get("from", ""))
        if normalise_email(from_addr) not in known_senders:
            continue
        body = extract_body(full["payload"])
        replies.append(
            {
                "sender": from_addr,
                "subject": headers.get("subject", ""),
                "body": body,
                "thread_id": full.get("threadId"),
                "message_id": full.get("id"),
            }
        )
    return replies


def extract_email(from_header: str) -> str:
    m = re.search(r"<([^>]+)>", from_header)
    return m.group(1) if m else from_header.strip()


def extract_body(payload: dict[str, Any]) -> str:
    import base64

    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        for part in payload["parts"]:  # fall back to HTML stripped
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", " ", html)
    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


# --- Reply drafting -----------------------------------------------------


def draft_reply(
    service,
    lead: dict[str, Any],
    classification: str,
    in_reply_to_message_id: str,
    thread_id: str,
) -> str | None:
    """Create a Gmail draft reply. Returns the draft id, or None if no reply."""
    body = build_reply_body(lead, classification)
    if not body:
        return None

    from email.mime.text import MIMEText
    import base64

    mime = MIMEText(body, "plain", "utf-8")
    mime["to"] = lead["email"]
    mime["subject"] = f"Re: {lead.get('last_subject', 'Following up')}"
    mime["In-Reply-To"] = in_reply_to_message_id
    mime["References"] = in_reply_to_message_id
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
        .execute()
    )
    return draft.get("id")


def build_reply_body(lead: dict[str, Any], classification: str) -> str | None:
    first_name = lead.get("first_name") or "there"
    concept = lead["concept_assigned"]
    concept_name = CONCEPT_NAMES[concept]

    if classification == "unsubscribe":
        return (
            f"Hi {first_name},\n\n"
            "Completely understood — I've removed you from any future emails. "
            "Apologies for the interruption.\n\n"
            "All the best,\nSheyi"
        )
    if classification == "not_interested":
        return (
            f"Hi {first_name},\n\n"
            "No worries at all — appreciate you taking the time to respond. "
            "If things change in the future, feel free to get in touch.\n\n"
            "All the best,\nSheyi"
        )
    if classification == "pricing_question":
        prices = CONCEPT_PRICES[concept]
        return (
            f"Hi {first_name},\n\n"
            "Great question. I'm actually testing a few price points to see what makes sense:\n\n"
            f"- £{prices['low']}/month — basic monitoring/features\n"
            f"- £{prices['mid']}/month — full features + alerts\n"
            f"- £{prices['high']}/month — everything + priority support\n\n"
            "Which tier feels right for what you'd need? Or does a completely "
            "different model (per user, per project, usage-based) make more sense "
            "for your team?\n\n"
            "No commitment — just figuring out the right structure.\n\n"
            "Sheyi"
        )
    if classification == "interested":
        return (
            f"Hi {first_name},\n\n"
            "Really appreciate the reply. That's exactly the kind of feedback I'm looking for.\n\n"
            "A couple of follow-ups if you don't mind:\n\n"
            "1. If a tool could solve the pain you mentioned, roughly how much time "
            "or money would it save your team per month?\n"
            "2. What would you realistically pay for something like that? "
            "(Totally informal — just trying to gauge whether the economics work.)\n"
            "3. Is there anything you've tried before that didn't work well enough?\n\n"
            "Thanks for being so helpful — this directly shapes what we build.\n\n"
            "Sheyi"
        )
    if classification == "question":
        return (
            f"Hi {first_name},\n\n"
            f"Good question — I'm Sheyi, founder of T&O Ventures. We're a small "
            f"product studio that builds software tools for businesses.\n\n"
            f"Right now I'm in research mode — talking to people like you to "
            f"understand whether {concept_name} would be something companies "
            f"would actually pay for before we build it.\n\n"
            f"Your perspective would be really valuable if you had a moment to share it.\n\n"
            f"Cheers,\nSheyi"
        )
    return None  # auto_reply handled separately (no draft)


# --- Orchestration ------------------------------------------------------


def process_replies(replies: list[dict[str, Any]], dry_run: bool = False) -> None:
    leads_data = load_json(LEADS_PATH)
    responses_data = load_json(RESPONSES_PATH) or {
        "metadata": {"total_responses": 0, "classifications": {}},
        "responses": [],
    }

    service = None if dry_run else get_gmail_service()

    for reply in replies:
        lead = find_lead_by_email(leads_data["leads"], reply["sender"])
        if not lead:
            log.info("Reply from unknown sender %s — skipping", reply["sender"])
            continue

        classification = classify(reply["body"])
        log.info(
            "[%s] %s from %s <%s>",
            classification,
            lead.get("company_name"),
            lead.get("first_name"),
            reply["sender"],
        )

        # Update lead state
        lead["response_status"] = classification
        lead["status"] = "responded"
        if classification == "unsubscribe":
            lead["status"] = "unsubscribed"
            add_to_suppression(reply["sender"], reason="unsubscribe_reply")
        elif classification == "not_interested":
            lead["status"] = "closed_not_interested"

        # Enrich local launch list with response data
        update_launch_list_response(
            email=reply["sender"],
            response_type=classification,
            response_notes=reply["body"][:280],
        )
        # Tag contact in EmailOctopus for launch segmentation
        update_emailoctopus_tag(reply["sender"], classification)

        # Record response
        responses_data["responses"].append(
            {
                "lead_id": lead["id"],
                "email": reply["sender"],
                "company_name": lead.get("company_name"),
                "concept": lead["concept_assigned"],
                "classification": classification,
                "received_date": now_iso(),
                "summary": reply["body"][:280],
                "thread_id": reply["thread_id"],
            }
        )
        responses_data["metadata"]["total_responses"] = len(responses_data["responses"])
        responses_data["metadata"].setdefault("classifications", {})
        responses_data["metadata"]["classifications"][classification] = (
            responses_data["metadata"]["classifications"].get(classification, 0) + 1
        )

        # Draft reply (not sent)
        if not dry_run and classification != "auto_reply":
            draft_id = draft_reply(
                service,
                lead,
                classification,
                reply["message_id"],
                reply["thread_id"],
            )
            if draft_id:
                log.info("Drafted reply (id=%s) — review in Gmail before sending", draft_id)

    save_json(LEADS_PATH, leads_data)
    save_json(RESPONSES_PATH, responses_data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Single poll then exit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--classify-only", action="store_true", help="Test classifier on stdin")
    args = parser.parse_args()

    if args.classify_only:
        text = sys.stdin.read()
        print("Classification:", classify(text))
        return 0

    leads_data = load_json(LEADS_PATH)
    known = {normalise_email(l["email"]) for l in leads_data.get("leads", [])}
    if not known:
        log.info("No leads in database. Nothing to monitor.")
        return 0

    if args.dry_run:
        log.info("Dry-run mode: skipping Gmail API and just validating script")
        return 0

    service = get_gmail_service()
    replies = fetch_unread_replies(service, known)
    log.info("Fetched %d unread replies from known senders", len(replies))
    process_replies(replies, dry_run=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
