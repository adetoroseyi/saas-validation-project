"""Enrich leads via Hunter.io — fill email gaps from Google Maps scraping.

Hunter.io is an email-finding service. You give it a company domain and a
person's name, and it returns the most likely work email address with a
confidence score. It's the ideal secondary layer for leads that came from
Google Maps with only a company name and website but no named contact.

This script does NOT source new companies — it enriches EXISTING leads in
leads.json that are missing a valid personal email (status == "needs_email").
It can also verify existing emails before they're sent.

WHEN TO USE
  Run after source_leads.py has populated leads from Google Maps.
  Any lead with first_name + website but no good email is a candidate.

HOW TO GET A HUNTER.IO API KEY
  1. Go to https://hunter.io and sign up (free account)
  2. Dashboard → API → copy your API key
  3. Add to .env: HUNTER_API_KEY=your_key_here
  4. Free tier: 25 searches/month + 50 verifications/month
     Starter ($34/month): 500 searches + 1,000 verifications/month
     Growth ($104/month): 5,000 searches

HOW HUNTER WORKS (two modes)
  Mode 1 — Domain search: give it a company domain, get ALL emails Hunter knows
    Endpoint: GET /v2/domain-search?domain=example.co.uk&type=personal
    Best for: finding the right person when you only have the company website

  Mode 2 — Email finder: give it domain + first name + last name
    Endpoint: GET /v2/email-finder?domain=example.co.uk&first_name=John&last_name=Smith
    Best for: confirming a contact from LinkedIn or Google Maps
    Returns email + confidence score (0-100). Accept at 80+.

Usage:
    python scripts/source_hunter.py                    # enrich all leads missing email
    python scripts/source_hunter.py --verify-existing  # verify emails already in leads.json
    python scripts/source_hunter.py --dry-run          # preview without saving
    python scripts/source_hunter.py --limit 25         # cap API calls (free tier: 25/month)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any
from urllib.parse import urlparse

import requests

from common import (
    LEADS_PATH,
    get_logger,
    is_valid_business_email,
    load_json,
    load_suppression_set,
    normalise_email,
    now_iso,
    save_json,
)

log = get_logger("source_hunter")

HUNTER_BASE = "https://api.hunter.io/v2"


# ── Hunter API helpers ────────────────────────────────────────────────────────

def extract_domain(url: str) -> str | None:
    """Extract clean domain from a URL. e.g. https://www.example.co.uk → example.co.uk"""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc or parsed.path
        return domain.lstrip("www.").lower() or None
    except Exception:
        return None


def domain_search(api_key: str, domain: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return up to `limit` personal email contacts known for this domain."""
    resp = requests.get(
        f"{HUNTER_BASE}/domain-search",
        params={
            "domain": domain,
            "type": "personal",
            "limit": limit,
            "api_key": api_key,
        },
        timeout=15,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {}).get("emails", [])


def email_finder(
    api_key: str,
    domain: str,
    first_name: str,
    last_name: str,
) -> dict[str, Any] | None:
    """Try to find a specific person's work email. Returns result or None."""
    resp = requests.get(
        f"{HUNTER_BASE}/email-finder",
        params={
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": api_key,
        },
        timeout=15,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    return data.get("data")


def verify_email(api_key: str, email: str) -> str:
    """Verify an email address. Returns status: valid / risky / invalid / unknown."""
    resp = requests.get(
        f"{HUNTER_BASE}/email-verifier",
        params={"email": email, "api_key": api_key},
        timeout=15,
    )
    if resp.status_code != 200:
        return "unknown"
    return resp.json().get("data", {}).get("status", "unknown")


# ── Lead enrichment logic ─────────────────────────────────────────────────────

def pick_best_email(emails: list[dict[str, Any]]) -> dict[str, Any] | None:
    """From a domain-search result, pick the most likely decision-maker email."""
    # Prefer 'personal' type, high confidence, and seniority markers in position
    SENIORITY_KEYWORDS = {
        "founder", "ceo", "coo", "director", "head", "manager",
        "owner", "partner", "principal", "vp", "president",
    }
    scored = []
    for e in emails:
        if e.get("type") != "personal":
            continue
        confidence = e.get("confidence", 0)
        position = (e.get("position") or "").lower()
        seniority_score = sum(1 for kw in SENIORITY_KEYWORDS if kw in position)
        scored.append((confidence + seniority_score * 10, e))
    if not scored:
        # Fallback: accept any type with high confidence
        scored = [(e.get("confidence", 0), e) for e in emails]
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-existing", action="store_true",
                        help="Verify emails already in leads.json instead of finding new ones")
    parser.add_argument("--min-confidence", type=int, default=75,
                        help="Minimum Hunter confidence score to accept (default 75)")
    parser.add_argument("--limit", type=int, default=25,
                        help="Max Hunter API calls this run (free tier: 25/month)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        log.error(
            "HUNTER_API_KEY not set in .env. "
            "Get a free key at hunter.io → Dashboard → API"
        )
        return 2

    leads_data = load_json(LEADS_PATH)
    if not leads_data or not leads_data.get("leads"):
        log.info("No leads in database. Run source_leads.py first.")
        return 0

    suppressed = load_suppression_set()
    calls_made = 0
    enriched_count = 0

    if args.verify_existing:
        # Mode: verify emails already in the database
        candidates = [
            l for l in leads_data["leads"]
            if l.get("email") and l.get("emails_sent", 0) == 0
            and l.get("email_verified") is None
        ]
        log.info("Verifying %d unverified leads (cap: %d)", len(candidates), args.limit)

        for lead in candidates:
            if calls_made >= args.limit:
                break
            status = verify_email(api_key, lead["email"])
            lead["email_verified"] = status
            lead["email_verified_at"] = now_iso()
            calls_made += 1
            log.info("%s → %s (%s)", lead["email"], status, lead["company_name"])

            if status == "invalid":
                lead["status"] = "invalid_email"
                log.warning("Marking %s as invalid_email", lead["email"])

            time.sleep(0.5)
    else:
        # Mode: find emails for leads that have a website but a generic/missing email
        existing_emails = {normalise_email(l["email"]) for l in leads_data["leads"]}

        candidates = [
            l for l in leads_data["leads"]
            if l.get("website")
            and (not l.get("email") or not is_valid_business_email(l.get("email", "")))
            and l.get("status") == "needs_email"
        ]
        log.info(
            "%d leads need email enrichment (cap: %d calls)",
            len(candidates), args.limit,
        )

        for lead in candidates:
            if calls_made >= args.limit:
                break

            domain = extract_domain(lead["website"])
            if not domain:
                continue

            found_email = None
            found_first_name = lead.get("first_name", "")
            found_last_name = lead.get("last_name", "")

            # If we have a full name, try email-finder first (more precise)
            if found_first_name and found_last_name:
                result = email_finder(api_key, domain, found_first_name, found_last_name)
                calls_made += 1
                if result:
                    confidence = result.get("confidence") or 0
                    candidate = normalise_email(result.get("email") or "")
                    if confidence >= args.min_confidence and is_valid_business_email(candidate):
                        found_email = candidate
                        log.info(
                            "Email-finder: %s (%s%%) for %s at %s",
                            found_email, confidence, found_first_name, domain,
                        )
                time.sleep(0.5)

            # Fallback: domain search
            if not found_email and calls_made < args.limit:
                emails = domain_search(api_key, domain, limit=5)
                calls_made += 1
                best = pick_best_email(emails)
                if best:
                    confidence = best.get("confidence") or 0
                    candidate = normalise_email(best.get("value") or "")
                    if confidence >= args.min_confidence and is_valid_business_email(candidate):
                        found_email = candidate
                        found_first_name = (best.get("first_name") or "").capitalize()
                        found_last_name = (best.get("last_name") or "").capitalize()
                        log.info(
                            "Domain-search: %s (%s%%) at %s",
                            found_email, confidence, domain,
                        )
                time.sleep(0.5)

            if not found_email or found_email in existing_emails or found_email in suppressed:
                continue

            if args.dry_run:
                log.info(
                    "DRY-RUN would update lead %s: email=%s",
                    lead.get("id"), found_email,
                )
                enriched_count += 1
                continue

            lead["email"] = found_email
            lead["first_name"] = found_first_name
            lead["last_name"] = found_last_name
            lead["status"] = "new"
            lead["email_source"] = "hunter"
            existing_emails.add(found_email)
            enriched_count += 1

    if not args.dry_run:
        leads_data["metadata"]["last_source_run"] = now_iso()
        save_json(LEADS_PATH, leads_data)

    log.info(
        "Done. Hunter calls made: %d. Leads enriched: %d.",
        calls_made, enriched_count,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
