"""Shared utilities for the SaaS Validation project.

Every script in scripts/ imports from here. Keep this file small and
dependency-light so the scripts remain portable.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Project paths (resolved relative to the repo root, which is the parent
# of the scripts/ directory).
REPO_ROOT = Path(__file__).resolve().parent.parent
LEADS_PATH = REPO_ROOT / "02-leads" / "leads.json"
SUPPRESSION_PATH = REPO_ROOT / "02-leads" / "suppression_list.json"
SENT_LOG_PATH = REPO_ROOT / "03-emails" / "sent_log.json"
RESPONSES_PATH = REPO_ROOT / "04-responses" / "responses.json"
TEMPLATES_DIR = REPO_ROOT / "03-emails" / "templates"
REPORTS_DIR = REPO_ROOT / "05-reports"
VALIDATED_DIR = REPO_ROOT / "06-validated"
LAUNCH_LIST_PATH = REPO_ROOT / "07-launch-list" / "launch_contacts.json"

# ---------------------------------------------------------------------------
# Industry peer mapping — used to resolve {{industry_peer}} in email templates.
# Keys are lowercase substrings to match against lead.industry.
# SIC codes (from Companies House) take priority over string matching.
# ---------------------------------------------------------------------------

SIC_TO_PEER: dict[str, str] = {
    "73110": "agency owner",       # Advertising agencies
    "73120": "agency owner",       # Media representation
    "70210": "consultant",         # PR activities
    "70220": "consultant",         # Business & management consultancy
    "62020": "IT consultant",      # IT consultancy
    "62090": "IT consultant",      # Other IT service activities
    "63110": "IT consultant",      # Data processing / hosting
    "78109": "recruiter",          # Other recruitment activities
    "78200": "recruiter",          # Temporary employment agency
    "78300": "recruiter",          # Human resources provision
    "74909": "consultant",         # Other professional activities n.e.c.
}

INDUSTRY_KEYWORD_TO_PEER: list[tuple[str, str]] = [
    # Checked in order — first match wins
    ("recruit",     "recruiter"),
    ("staffing",    "recruiter"),
    ("headhunt",    "recruiter"),
    ("it consult",  "IT consultant"),
    ("tech consult","IT consultant"),
    ("software",    "IT consultant"),
    ("web dev",     "IT consultant"),
    ("it service",  "IT consultant"),
    ("management consult", "consultant"),
    ("business consult",   "consultant"),
    ("strategy consult",   "consultant"),
    ("agency",      "agency owner"),
    ("marketing",   "agency owner"),
    ("advertis",    "agency owner"),
    ("creative",    "agency owner"),
    ("media",       "agency owner"),
    ("pr ",         "consultant"),
]


def resolve_industry_peer(lead: dict) -> str:
    """Return the correct {{industry_peer}} value for a Concept B lead.

    Priority order:
    1. SIC code from lead data (most precise)
    2. Industry string keyword matching
    3. Default fallback
    """
    sic = str(lead.get("sic_code") or "").strip()
    if sic and sic in SIC_TO_PEER:
        return SIC_TO_PEER[sic]

    industry = (lead.get("industry") or "").lower()
    for keyword, peer in INDUSTRY_KEYWORD_TO_PEER:
        if keyword in industry:
            return peer

    return "service business owner"


CONCEPTS = ["A", "B", "C", "D"]
CONCEPT_NAMES = {
    "A": "ComplianceWatch",
    "B": "LeadPulse",
    "C": "MetricShield",
    "D": "ProcessFlow",
}
CONCEPT_PRICES = {
    "A": {"low": 49, "mid": 99, "high": 199},
    "B": {"low": 29, "mid": 79, "high": 149},
    "C": {"low": 39, "mid": 99, "high": 199},
    "D": {"low": 59, "mid": 129, "high": 249},
}

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_date() -> str:
    """Current date in YYYY-MM-DD (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file, returning {} if the file is missing."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON to disk with 2-space indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def normalise_email(email: str) -> str:
    """Lowercase and strip whitespace from an email address."""
    return (email or "").strip().lower()


EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
GENERIC_LOCAL_PARTS = {
    "info",
    "contact",
    "hello",
    "admin",
    "office",
    "sales",
    "support",
    "help",
    "enquiries",
    "enquiry",
    "team",
    "noreply",
    "no-reply",
    "donotreply",
    "mail",
    "general",
}


def is_valid_business_email(email: str) -> bool:
    """Basic business-email qualification: real format, not generic inbox."""
    email = normalise_email(email)
    if not EMAIL_RE.match(email):
        return False
    local = email.split("@", 1)[0]
    if local in GENERIC_LOCAL_PARTS:
        return False
    # Personal email providers are disqualified — we want company domains
    domain = email.split("@", 1)[1]
    personal_domains = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "protonmail.com",
        "live.com",
        "msn.com",
        "yandex.com",
    }
    if domain in personal_domains:
        return False
    return True


def next_concept(metadata: dict[str, Any]) -> str:
    """Round-robin concept assignment. Mutates metadata in place."""
    idx = metadata.get("last_concept_index", -1) + 1
    concept = CONCEPTS[idx % len(CONCEPTS)]
    metadata["last_concept_index"] = idx
    metadata.setdefault("concept_counts", {c: 0 for c in CONCEPTS})
    metadata["concept_counts"][concept] = metadata["concept_counts"].get(concept, 0) + 1
    return concept


def load_suppression_set() -> set[str]:
    """Return the set of suppressed email addresses (all lowercase)."""
    data = load_json(SUPPRESSION_PATH)
    return {normalise_email(e["email"]) for e in data.get("suppressed", [])}


def add_to_suppression(email: str, reason: str = "unsubscribe") -> None:
    """Add an email to the suppression list. Idempotent."""
    email = normalise_email(email)
    data = load_json(SUPPRESSION_PATH)
    data.setdefault("metadata", {})
    data.setdefault("suppressed", [])
    existing = {normalise_email(e["email"]) for e in data["suppressed"]}
    if email in existing:
        return
    data["suppressed"].append(
        {"email": email, "reason": reason, "added": now_iso()}
    )
    data["metadata"]["count"] = len(data["suppressed"])
    save_json(SUPPRESSION_PATH, data)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Launch list — product launch email database
# Populated automatically: Email 1 send → contact added.
# Response → interest_level and response_type enriched.
# ---------------------------------------------------------------------------

def _load_launch_list() -> dict:
    """Load launch_contacts.json, initialising if missing."""
    if not LAUNCH_LIST_PATH.exists():
        return {
            "metadata": {
                "created": now_iso(),
                "project": "T&O Ventures SaaS Validation",
                "description": (
                    "Master launch list. Every contact reached during validation "
                    "is saved here, enriched with response data, ready for product "
                    "launch outreach."
                ),
                "total_contacts": 0,
                "last_updated": None,
            },
            "contacts": [],
        }
    with LAUNCH_LIST_PATH.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def add_to_launch_list(lead: dict, concept_name: str) -> None:
    """Add a lead to the launch list when Email 1 is first sent.

    Idempotent — if the lead's email already exists in the list, skips.
    """
    email = normalise_email(lead.get("email", ""))
    if not email:
        return

    data = _load_launch_list()
    existing_emails = {normalise_email(c["email"]) for c in data["contacts"]}
    if email in existing_emails:
        return  # already on the list

    # Generate sequential contact id
    count = len(data["contacts"]) + 1
    contact_id = f"lc_{count:06d}"

    data["contacts"].append({
        "id": contact_id,
        "lead_id": lead.get("id"),
        "email": email,
        "first_name": lead.get("first_name") or "",
        "last_name": lead.get("last_name") or "",
        "company_name": lead.get("company_name") or "",
        "industry": lead.get("industry") or "",
        "job_title": lead.get("job_title") or "",
        "website": lead.get("website") or "",
        "city": lead.get("city") or "",
        "country": lead.get("country") or "GB",
        "concept_tested": lead.get("concept_assigned"),
        "concept_name": concept_name,
        "interest_level": "unknown",   # updated when reply arrives
        "response_type": None,         # interested | pricing_question | question |
                                       # not_interested | unsubscribed | auto_reply | no_reply
        "response_notes": None,
        "added_to_list_date": now_iso(),
        "last_interaction_date": now_iso(),
        "launch_segment": None,        # early_access | beta_invite | standard — set at launch
        "do_not_contact": False,
    })

    data["metadata"]["total_contacts"] = len(data["contacts"])
    data["metadata"]["last_updated"] = now_iso()

    LAUNCH_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_json(LAUNCH_LIST_PATH, data)


def push_to_emailoctopus(lead: dict, concept_name: str) -> bool:
    """Push a contact to EmailOctopus when Email 1 is sent.

    Requires EMAILOCTOPUS_API_KEY and EMAILOCTOPUS_LIST_ID in .env.
    Silently skips (returns False) if the keys are not set — never
    crashes the send pipeline over a list-sync failure.

    Tags the contact with their concept so you can segment at launch:
        concept-a | concept-b | concept-c | concept-d
    """
    api_key = os.getenv("EMAILOCTOPUS_API_KEY")
    list_id = os.getenv("EMAILOCTOPUS_LIST_ID")
    if not api_key or not list_id:
        return False

    try:
        import requests  # type: ignore
    except ImportError:
        return False

    concept_code = (lead.get("concept_assigned") or "").upper()
    tag = f"concept-{concept_code.lower()}" if concept_code else None

    payload: dict = {
        "api_key": api_key,
        "email_address": lead.get("email", ""),
        "fields": {
            "FirstName": lead.get("first_name") or "",
            "LastName":  lead.get("last_name")  or "",
            "Company":   lead.get("company_name") or "",
            "Industry":  lead.get("industry")    or "",
            "Concept":   concept_name,
            "JobTitle":  lead.get("job_title")   or "",
            "City":      lead.get("city")         or "",
        },
        "status": "SUBSCRIBED",
    }
    if tag:
        payload["tags"] = [tag]

    log = get_logger("emailoctopus")
    try:
        resp = requests.post(
            f"https://emailoctopus.com/api/1.6/lists/{list_id}/contacts",
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            log.info("EmailOctopus: added %s", lead.get("email"))
            return True
        # 409 = already on the list — not an error
        if resp.status_code == 409:
            log.info("EmailOctopus: %s already on list", lead.get("email"))
            return True
        log.warning("EmailOctopus: unexpected status %s — %s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        log.warning("EmailOctopus push failed (non-fatal): %s", exc)
        return False


def update_emailoctopus_tag(email: str, tag: str) -> bool:
    """Add a tag to an existing EmailOctopus contact (e.g. 'interested', 'pricing').

    Used by monitor_responses.py to enrich contacts when replies arrive.
    Non-fatal — never crashes the response pipeline.
    """
    api_key = os.getenv("EMAILOCTOPUS_API_KEY")
    list_id = os.getenv("EMAILOCTOPUS_LIST_ID")
    if not api_key or not list_id:
        return False

    try:
        import requests  # type: ignore
    except ImportError:
        return False

    log = get_logger("emailoctopus")
    try:
        # First find the contact id by email
        resp = requests.get(
            f"https://emailoctopus.com/api/1.6/lists/{list_id}/contacts/{email}",
            params={"api_key": api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("EmailOctopus: contact %s not found (%s)", email, resp.status_code)
            return False

        contact_id = resp.json().get("id")
        if not contact_id:
            return False

        # Update the contact with the new tag
        update_resp = requests.put(
            f"https://emailoctopus.com/api/1.6/lists/{list_id}/contacts/{contact_id}",
            json={"api_key": api_key, "tags": [tag]},
            timeout=15,
        )
        if update_resp.status_code == 200:
            log.info("EmailOctopus: tagged %s as '%s'", email, tag)
            return True
        log.warning("EmailOctopus tag update failed: %s", update_resp.text[:200])
        return False
    except Exception as exc:
        log.warning("EmailOctopus tag update failed (non-fatal): %s", exc)
        return False


def update_launch_list_response(
    email: str,
    response_type: str,
    response_notes: str = "",
) -> None:
    """Enrich a launch list contact with their reply classification.

    Called by monitor_responses.py when a reply is processed.

    response_type values:
        interested | pricing_question | question |
        not_interested | unsubscribed | auto_reply | no_reply
    """
    email = normalise_email(email)
    if not email:
        return

    data = _load_launch_list()
    updated = False

    # Map response type to interest level
    interest_map = {
        "interested":        "high",
        "pricing_question":  "high",
        "question":          "medium",
        "auto_reply":        "unknown",
        "not_interested":    "none",
        "unsubscribed":      "none",
        "no_reply":          "low",
    }

    for contact in data["contacts"]:
        if normalise_email(contact["email"]) == email:
            contact["response_type"] = response_type
            contact["interest_level"] = interest_map.get(response_type, "unknown")
            contact["response_notes"] = response_notes
            contact["last_interaction_date"] = now_iso()
            # Mark unsubscribers so they are never emailed at launch
            if response_type == "unsubscribed":
                contact["do_not_contact"] = True
            updated = True
            break

    if updated:
        data["metadata"]["last_updated"] = now_iso()
        save_json(LAUNCH_LIST_PATH, data)
