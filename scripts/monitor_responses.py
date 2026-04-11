"""Poll Gmail for replies, classify them, and auto-send responses.

Two modes depending on environment:

  SMTP mode (GitHub Actions):
    - USE_SMTP=1
    - Reads inbox via IMAP (imap.gmail.com) using GMAIL_APP_PASSWORD
    - Sends replies via SMTP (smtp.gmail.com) using GMAIL_APP_PASSWORD
    - Fully automated — no human in the loop

  Gmail API mode (local / supervised):
    - USE_SMTP=0 (default)
    - Reads inbox via Gmail API (requires token.json OAuth)
    - Creates DRAFT replies only — human reviews before sending

AUTO_SEND_REPLIES=1 forces auto-sending in either mode.
AUTO_SEND_REPLIES=0 always creates drafts (safe/supervised mode).

Replies are NEVER sent to auto_reply (out-of-office) classifications.

Usage:
    python scripts/monitor_responses.py --once
    python scripts/monitor_responses.py --classify-only   # test classifier on stdin
"""

from __future__ import annotations

import argparse
import base64
import email as email_lib
import imaplib
import os
import re
import smtplib
import sys
import time
from email.mime.text import MIMEText
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

SENDING_EMAIL = os.getenv("SENDING_EMAIL", "sheyi@trysignalbench.com")
SENDING_NAME  = os.getenv("SENDING_NAME",  "Sheyi Olu")
USE_SMTP      = os.getenv("USE_SMTP", "0") == "1"
AUTO_SEND     = os.getenv("AUTO_SEND_REPLIES", "1") == "1"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

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
    return "question"


# ---------------------------------------------------------------------------
# Lead lookup
# ---------------------------------------------------------------------------

def find_lead_by_email(leads: list[dict], email: str) -> dict | None:
    email = normalise_email(email)
    for lead in leads:
        if normalise_email(lead["email"]) == email:
            return lead
    return None


# ---------------------------------------------------------------------------
# IMAP inbox reader (GitHub Actions / SMTP mode)
# ---------------------------------------------------------------------------

def fetch_unread_replies_imap(known_senders: set[str]) -> list[dict]:
    """Fetch unread replies via IMAP using the Gmail App Password.

    Returns list of dicts: {sender, subject, body, message_id, in_reply_to}
    Marks fetched messages as read so they are not re-processed.
    """
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not app_password:
        raise SystemExit("GMAIL_APP_PASSWORD not set — cannot check inbox via IMAP.")

    replies = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(SENDING_EMAIL, app_password)
        mail.select("INBOX")

        _, msg_nums = mail.search(None, "UNSEEN")
        ids = msg_nums[0].split() if msg_nums[0] else []
        log.info("IMAP: %d unseen messages in inbox", len(ids))

        for num in ids:
            _, data = mail.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = email_lib.message_from_bytes(raw)

            from_header = msg.get("From", "")
            sender = _extract_email_addr(from_header)

            if normalise_email(sender) not in known_senders:
                # Mark as read anyway so we don't keep seeing it
                mail.store(num, "+FLAGS", "\\Seen")
                continue

            body = _extract_imap_body(msg)
            replies.append({
                "sender":     sender,
                "subject":    msg.get("Subject", ""),
                "body":       body,
                "message_id": msg.get("Message-ID", ""),
                "in_reply_to": msg.get("In-Reply-To", ""),
                "thread_id":  msg.get("References", msg.get("Message-ID", "")),
            })
            # Mark as read
            mail.store(num, "+FLAGS", "\\Seen")

        mail.logout()
    except Exception as exc:
        log.error("IMAP error: %s", exc)
    return replies


def _extract_email_addr(header: str) -> str:
    m = re.search(r"<([^>]+)>", header)
    return m.group(1) if m else header.strip()


def _extract_imap_body(msg) -> str:
    """Extract plain-text body from a parsed email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="ignore")
        # Fall back to HTML stripped
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="ignore")
                return re.sub(r"<[^>]+>", " ", html)
    else:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="ignore")
    return ""


# ---------------------------------------------------------------------------
# Gmail API inbox reader (local / supervised mode)
# ---------------------------------------------------------------------------

def get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from googleapiclient.discovery import build       # type: ignore
    except ImportError:
        raise SystemExit("google-api-python-client not installed.")
    from pathlib import Path as _P
    token_path = _P(__file__).parent / "token.json"
    creds = Credentials.from_authorized_user_file(
        str(token_path),
        ["https://www.googleapis.com/auth/gmail.readonly",
         "https://www.googleapis.com/auth/gmail.compose",
         "https://www.googleapis.com/auth/gmail.send"],
    )
    return build("gmail", "v1", credentials=creds)


def fetch_unread_replies_api(service, known_senders: set[str]) -> list[dict]:
    results  = service.users().messages().list(userId="me", q="is:unread in:inbox").execute()
    messages = results.get("messages", [])
    replies  = []
    for m in messages:
        full    = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        sender  = _extract_email_addr(headers.get("from", ""))
        if normalise_email(sender) not in known_senders:
            continue
        body = _extract_gmail_api_body(full["payload"])
        replies.append({
            "sender":      sender,
            "subject":     headers.get("subject", ""),
            "body":        body,
            "message_id":  full.get("id", ""),
            "in_reply_to": headers.get("in-reply-to", ""),
            "thread_id":   full.get("threadId", ""),
        })
    return replies


def _extract_gmail_api_body(payload: dict) -> str:
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        for part in payload["parts"]:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                return re.sub(r"<[^>]+>", " ", html)
    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


# ---------------------------------------------------------------------------
# Reply content builder
# ---------------------------------------------------------------------------

def build_reply_body(lead: dict, classification: str) -> str | None:
    first_name   = lead.get("first_name") or "there"
    concept      = lead["concept_assigned"]
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
            "Great question. I'm testing a few price points to see what makes sense:\n\n"
            f"- £{prices['low']}/month — core features\n"
            f"- £{prices['mid']}/month — full features + alerts\n"
            f"- £{prices['high']}/month — everything + priority support\n\n"
            "Which tier feels closest to what you'd need? Or does a different "
            "model (per user, per project, usage-based) make more sense for your team?\n\n"
            "No commitment — just figuring out the right structure.\n\n"
            "Sheyi"
        )
    if classification == "interested":
        return (
            f"Hi {first_name},\n\n"
            "Really appreciate the reply — that's exactly the kind of feedback I'm looking for.\n\n"
            "A couple of quick follow-ups if you don't mind:\n\n"
            "1. If a tool solved the pain you mentioned, roughly how much time or money "
            "would it save your team per month?\n"
            "2. What would you realistically pay for something like that? "
            "(Totally informal — just trying to gauge whether the economics work.)\n"
            "3. Is there anything you've tried before that didn't quite work?\n\n"
            "Thanks — this directly shapes what we build.\n\n"
            "Sheyi"
        )
    if classification == "question":
        return (
            f"Hi {first_name},\n\n"
            f"Good question — I'm Sheyi, founder of T&O Ventures, a small product studio "
            f"that builds software tools for UK businesses.\n\n"
            f"Right now I'm in research mode — talking to people like you to understand "
            f"whether {concept_name} is something companies would actually pay for "
            f"before we commit to building it.\n\n"
            f"Your perspective would be genuinely valuable if you have a moment.\n\n"
            f"Cheers,\nSheyi"
        )
    return None  # auto_reply — no response sent


# ---------------------------------------------------------------------------
# Reply senders
# ---------------------------------------------------------------------------

def send_reply_smtp(to_email: str, subject: str, body: str, in_reply_to: str = "") -> bool:
    """Send a reply via SMTP (GitHub Actions mode)."""
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not app_password:
        log.error("GMAIL_APP_PASSWORD not set — cannot send reply")
        return False
    try:
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"]      = to_email
        mime["From"]    = f"{SENDING_NAME} <{SENDING_EMAIL}>"
        mime["Subject"] = reply_subject
        if in_reply_to:
            mime["In-Reply-To"] = in_reply_to
            mime["References"]  = in_reply_to
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(SENDING_EMAIL, app_password)
            server.send_message(mime)
        log.info("Auto-reply sent to %s", to_email)
        return True
    except Exception as exc:
        log.error("Failed to send reply to %s: %s", to_email, exc)
        return False


def send_reply_api(service, lead: dict, subject: str, body: str,
                   in_reply_to: str, thread_id: str) -> bool:
    """Send a reply via Gmail API (local mode)."""
    try:
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"]      = lead["email"]
        mime["From"]    = f"{SENDING_NAME} <{SENDING_EMAIL}>"
        mime["Subject"] = reply_subject
        if in_reply_to:
            mime["In-Reply-To"] = in_reply_to
            mime["References"]  = in_reply_to
        raw  = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        service.users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": thread_id}
        ).execute()
        log.info("Auto-reply sent via Gmail API to %s", lead["email"])
        return True
    except Exception as exc:
        log.error("Gmail API send failed: %s", exc)
        return False


def draft_reply_api(service, lead: dict, subject: str, body: str,
                    in_reply_to: str, thread_id: str) -> str | None:
    """Create a Gmail draft (supervised mode fallback)."""
    try:
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"]      = lead["email"]
        mime["Subject"] = reply_subject
        if in_reply_to:
            mime["In-Reply-To"] = in_reply_to
            mime["References"]  = in_reply_to
        raw   = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": thread_id}}
        ).execute()
        return draft.get("id")
    except Exception as exc:
        log.error("Draft creation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

def process_replies(replies: list[dict], service=None, dry_run: bool = False) -> None:
    leads_data = load_json(LEADS_PATH)
    responses_data = load_json(RESPONSES_PATH) or {
        "metadata": {"total_responses": 0, "classifications": {}},
        "responses": [],
    }

    for reply in replies:
        lead = find_lead_by_email(leads_data["leads"], reply["sender"])
        if not lead:
            log.info("Reply from unknown sender %s — skipping", reply["sender"])
            continue

        classification = classify(reply["body"])
        log.info("[%s] %s <%s>", classification, lead.get("company_name"), reply["sender"])

        # Update lead state
        lead["response_status"] = classification
        lead["status"] = "responded"
        if classification == "unsubscribe":
            lead["status"] = "unsubscribed"
            add_to_suppression(reply["sender"], reason="unsubscribe_reply")
        elif classification == "not_interested":
            lead["status"] = "closed_not_interested"

        # Enrich launch list and EmailOctopus
        update_launch_list_response(
            email=reply["sender"],
            response_type=classification,
            response_notes=reply["body"][:280],
        )
        update_emailoctopus_tag(reply["sender"], classification)

        # Record response
        responses_data["responses"].append({
            "lead_id":        lead["id"],
            "email":          reply["sender"],
            "company_name":   lead.get("company_name"),
            "concept":        lead["concept_assigned"],
            "classification": classification,
            "received_date":  now_iso(),
            "summary":        reply["body"][:280],
            "thread_id":      reply.get("thread_id", ""),
        })
        responses_data["metadata"]["total_responses"] = len(responses_data["responses"])
        responses_data["metadata"].setdefault("classifications", {})
        responses_data["metadata"]["classifications"][classification] = (
            responses_data["metadata"]["classifications"].get(classification, 0) + 1
        )

        # Send / draft reply
        if dry_run or classification == "auto_reply":
            if classification != "auto_reply":
                log.info("DRY-RUN: would send %s reply to %s", classification, reply["sender"])
            continue

        reply_body = build_reply_body(lead, classification)
        if not reply_body:
            continue

        if AUTO_SEND:
            # Fully automated
            if USE_SMTP:
                send_reply_smtp(
                    to_email    = reply["sender"],
                    subject     = reply["subject"],
                    body        = reply_body,
                    in_reply_to = reply.get("in_reply_to") or reply.get("message_id", ""),
                )
            elif service:
                send_reply_api(
                    service      = service,
                    lead         = lead,
                    subject      = reply["subject"],
                    body         = reply_body,
                    in_reply_to  = reply.get("in_reply_to") or reply.get("message_id", ""),
                    thread_id    = reply.get("thread_id", ""),
                )
        else:
            # Supervised — create draft only
            if service:
                draft_id = draft_reply_api(
                    service      = service,
                    lead         = lead,
                    subject      = reply["subject"],
                    body         = reply_body,
                    in_reply_to  = reply.get("in_reply_to") or reply.get("message_id", ""),
                    thread_id    = reply.get("thread_id", ""),
                )
                if draft_id:
                    log.info("Draft created (id=%s) — review in Gmail before sending", draft_id)

        # Throttle between replies to avoid rate limits
        time.sleep(3)

    save_json(LEADS_PATH, leads_data)
    save_json(RESPONSES_PATH, responses_data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once",          action="store_true", help="Single poll then exit")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--classify-only", action="store_true", help="Test classifier on stdin")
    args = parser.parse_args()

    if args.classify_only:
        print("Classification:", classify(sys.stdin.read()))
        return 0

    leads_data = load_json(LEADS_PATH)
    known = {normalise_email(l["email"]) for l in leads_data.get("leads", [])}
    if not known:
        log.info("No leads in database. Nothing to monitor.")
        return 0

    log.info("Mode: %s | Auto-send: %s",
             "SMTP/IMAP" if USE_SMTP else "Gmail API",
             "YES" if AUTO_SEND else "NO (drafts only)")

    if USE_SMTP:
        replies = fetch_unread_replies_imap(known)
        log.info("%d replies from known leads", len(replies))
        process_replies(replies, service=None, dry_run=args.dry_run)
    else:
        service = get_gmail_service()
        replies = fetch_unread_replies_api(service, known)
        log.info("%d replies from known leads", len(replies))
        process_replies(replies, service=service, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
