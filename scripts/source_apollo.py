"""Source leads from Apollo.io People Search API.

Apollo is a B2B contact database with 275M+ verified contacts. Unlike Google
Maps (which finds companies then hunts for emails), Apollo starts with named
people — so every result is already a qualified contact with a verified email.

This script runs ALONGSIDE source_leads.py. Each provides a different mix:
  - Google Maps:  strong on local UK/EU SMEs, varies in email quality
  - Apollo:       global reach, consistent email quality, named decision-makers

HOW TO GET AN APOLLO API KEY
  1. Go to https://app.apollo.io and sign up (free account is fine to start)
  2. Settings → Integrations → API → Create new API key
  3. Add to .env: APOLLO_API_KEY=your_key_here
  4. Free tier: 50 exports/month — useful for testing
     Basic plan ($49/month): ~10,000 exports/month — enough for the full pipeline

SEARCH PROFILES
  Each profile maps one SaaS concept to a set of job titles + industries.
  The idea: find people who feel the exact pain the concept solves.

  Concept A (ComplianceWatch)  → compliance/risk/operations titles in regulated industries
  Concept B (LeadPulse)        → founder/BD/sales titles in service businesses
  Concept C (MetricShield)     → owner/operations/finance titles in SMEs
  Concept D (ProcessFlow)      → operations/process/COO titles in manual-process industries

Usage:
    python scripts/source_apollo.py                    # default: all profiles, round-robin
    python scripts/source_apollo.py --concept B        # only LeadPulse profile
    python scripts/source_apollo.py --limit 50         # cap total leads saved
    python scripts/source_apollo.py --dry-run          # preview without saving
    python scripts/source_apollo.py --page 2           # start from page 2 (pagination)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import requests

from common import (
    CONCEPTS,
    LEADS_PATH,
    get_logger,
    is_valid_business_email,
    load_json,
    load_suppression_set,
    next_concept,
    normalise_email,
    now_iso,
    save_json,
    today_date,
)

log = get_logger("source_apollo")

APOLLO_BASE = "https://api.apollo.io/v1"
APOLLO_PEOPLE_SEARCH = f"{APOLLO_BASE}/mixed_people/search"

# ── Search profiles (one per concept) ────────────────────────────────────────

PROFILES: dict[str, dict[str, Any]] = {
    "A": {
        "label": "ComplianceWatch",
        "person_titles": [
            "compliance manager",
            "compliance officer",
            "risk manager",
            "head of compliance",
            "regulatory affairs manager",
            "quality assurance manager",
            "operations director",
            "chief operating officer",
            "COO",
            "finance director",
            "CFO",
        ],
        "organization_industry_tag_ids": [],
        # Use keyword tags instead — cleaner for SME targeting
        "q_organization_keyword_tags": [
            "financial services",
            "healthcare",
            "construction",
            "food and beverage",
            "legal services",
            "recruitment",
            "manufacturing",
        ],
        "organization_num_employees_ranges": ["10,500"],
        "locations": [
            "United Kingdom",
            "United States",
            "Canada",
            "Australia",
        ],
    },
    "B": {
        "label": "LeadPulse",
        "person_titles": [
            "founder",
            "co-founder",
            "CEO",
            "managing director",
            "head of business development",
            "business development manager",
            "head of growth",
            "growth manager",
            "sales director",
            "commercial director",
        ],
        "q_organization_keyword_tags": [
            "marketing agency",
            "digital agency",
            "consulting",
            "recruitment agency",
            "IT services",
            "PR agency",
            "accounting firm",
            "design agency",
        ],
        "organization_num_employees_ranges": ["2,100"],
        "locations": [
            "United Kingdom",
            "United States",
            "Canada",
            "Australia",
            "Ireland",
        ],
    },
    "C": {
        "label": "MetricShield",
        "person_titles": [
            "owner",
            "managing director",
            "general manager",
            "operations manager",
            "head of operations",
            "COO",
            "finance director",
            "CFO",
            "business owner",
        ],
        "q_organization_keyword_tags": [
            "retail",
            "ecommerce",
            "hospitality",
            "property management",
            "logistics",
            "professional services",
            "distribution",
        ],
        "organization_num_employees_ranges": ["10,500"],
        "locations": [
            "United Kingdom",
            "United States",
            "Canada",
            "Australia",
            "Germany",
            "Netherlands",
        ],
    },
    "D": {
        "label": "ProcessFlow",
        "person_titles": [
            "operations manager",
            "head of operations",
            "COO",
            "process manager",
            "operations director",
            "business analyst",
            "project manager",
            "head of delivery",
            "director of operations",
        ],
        "q_organization_keyword_tags": [
            "logistics",
            "professional services",
            "legal",
            "healthcare administration",
            "real estate",
            "insurance",
            "managed services",
        ],
        "organization_num_employees_ranges": ["20,500"],
        "locations": [
            "United Kingdom",
            "United States",
            "Canada",
            "Australia",
        ],
    },
}


# ── Apollo API helpers ────────────────────────────────────────────────────────

def search_people(
    api_key: str,
    profile: dict[str, Any],
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    """Call Apollo /mixed_people/search and return the raw JSON response."""
    payload = {
        "api_key": api_key,
        "page": page,
        "per_page": per_page,
        "person_titles": profile["person_titles"],
        "person_locations": profile["locations"],
        "organization_num_employees_ranges": profile["organization_num_employees_ranges"],
        "contact_email_status": ["verified", "likely to engage"],
    }
    # Add keyword tags if specified
    if profile.get("q_organization_keyword_tags"):
        payload["q_organization_keyword_tags"] = profile["q_organization_keyword_tags"]

    resp = requests.post(
        APOLLO_PEOPLE_SEARCH,
        json=payload,
        headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_lead_from_person(person: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an Apollo person record into our lead schema."""
    email = normalise_email(person.get("email") or "")
    if not is_valid_business_email(email):
        return None

    org = person.get("organization") or person.get("employment_history", [{}])[0] if not person.get("organization") else person.get("organization")
    if isinstance(org, list):
        org = org[0] if org else {}

    company_name = (
        person.get("organization_name")
        or (org.get("name") if org else None)
        or ""
    )
    website = (org.get("website_url") or "") if org else ""
    if not company_name:
        return None

    country = (
        person.get("country")
        or (org.get("country") if org else "")
        or ""
    )
    city = (
        person.get("city")
        or (org.get("city") if org else "")
        or ""
    )

    # Employee count — Apollo often has this directly
    emp_count = (org.get("num_employees") or 0) if org else 0
    if emp_count >= 100:
        employee_estimate = "100-500"
    elif emp_count >= 20:
        employee_estimate = "20-100"
    else:
        employee_estimate = "5-20"

    industry = (org.get("industry") or "") if org else ""

    return {
        "company_name": company_name,
        "industry": industry or "Unknown",
        "country": country,
        "city": city,
        "email": email,
        "first_name": (person.get("first_name") or "").strip().capitalize(),
        "last_name": (person.get("last_name") or "").strip().capitalize(),
        "job_title": person.get("title") or "",
        "website": website,
        "employee_estimate": employee_estimate,
        "source": "apollo",
        "sourced_date": today_date(),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concept", choices=CONCEPTS, default=None,
                        help="Run only this concept's profile")
    parser.add_argument("--limit", type=int, default=100,
                        help="Max total leads to save this run")
    parser.add_argument("--page", type=int, default=1,
                        help="Apollo results page to start from")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        log.error(
            "APOLLO_API_KEY not set in .env. "
            "Get one free at: app.apollo.io → Settings → Integrations → API"
        )
        return 2

    # Load existing state
    leads_data = load_json(LEADS_PATH) or {
        "metadata": {"total_sourced": 0, "last_concept_index": -1, "concept_counts": {}},
        "leads": [],
    }
    existing_emails = {normalise_email(l["email"]) for l in leads_data["leads"]}
    suppressed = load_suppression_set()

    # Decide which profiles to run
    profiles_to_run = [args.concept] if args.concept else CONCEPTS

    new_leads: list[dict[str, Any]] = []

    for concept in profiles_to_run:
        if len(new_leads) >= args.limit:
            break

        profile = PROFILES[concept]
        log.info(
            "Searching Apollo for concept %s (%s) — page %d",
            concept, profile["label"], args.page,
        )

        try:
            result = search_people(api_key, profile, page=args.page)
        except requests.HTTPError as e:
            log.error("Apollo API error for concept %s: %s", concept, e)
            if e.response is not None and e.response.status_code == 401:
                log.error("Invalid API key — check APOLLO_API_KEY in .env")
                return 2
            continue

        people = result.get("people") or []
        pagination = result.get("pagination") or {}
        log.info(
            "Apollo returned %d people (total available: %s)",
            len(people),
            pagination.get("total_entries", "?"),
        )

        for person in people:
            if len(new_leads) >= args.limit:
                break

            lead = extract_lead_from_person(person)
            if not lead:
                continue
            if lead["email"] in existing_emails or lead["email"] in suppressed:
                continue

            lead["id"] = f"lead_{leads_data['metadata'].get('total_sourced', 0) + len(new_leads) + 1:06d}"
            lead["concept_assigned"] = next_concept(leads_data["metadata"])
            lead["status"] = "new"
            lead["emails_sent"] = 0
            lead["last_email_date"] = None
            lead["response_status"] = None
            lead["notes"] = f"Apollo: {lead['job_title']} @ {lead['company_name']}"

            new_leads.append(lead)
            existing_emails.add(lead["email"])

        # Respect Apollo rate limits — 1 request/sec on free tier
        time.sleep(1.2)

    log.info("Found %d new qualified leads from Apollo", len(new_leads))

    if args.dry_run:
        for lead in new_leads[:5]:
            log.info(
                "DRY-RUN: %s %s (%s) <%s> — concept %s",
                lead["first_name"], lead["last_name"],
                lead["job_title"], lead["email"],
                lead["concept_assigned"],
            )
        return 0

    leads_data["leads"].extend(new_leads)
    leads_data["metadata"]["total_sourced"] = len(leads_data["leads"])
    leads_data["metadata"]["last_source_run"] = now_iso()
    save_json(LEADS_PATH, leads_data)
    log.info("Saved. Total leads in database: %d", len(leads_data["leads"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
