"""Source UK leads from Companies House API (FREE — government database).

Companies House is the UK's official register of every limited company
(5+ million). It's completely free, has no rate limits beyond basic
throttling, and returns the names of every director — real people
with real names you can email-find via Hunter.io.

Why this is powerful:
  - Every lead is a UK-registered limited company (legitimate, verifiable)
  - You get the actual director's name — not just a generic inbox
  - SIC codes let you target exact industries for each concept
  - Companies with 1-3 directors are almost always owner-managed SMEs
    (perfect ICPs for all 4 concepts)

WORKFLOW
  1. Search Companies House by SIC code (industry) + incorporation date
  2. Get company officers (directors) — real names
  3. Feed director name + company domain → Hunter.io email-finder
  4. Save qualified leads to leads.json

HOW TO GET A COMPANIES HOUSE API KEY
  1. Go to https://developer.company-information.service.gov.uk
  2. Sign in with a GOV.UK account (free)
  3. Create an application → get a live API key
  4. Add to .env: COMPANIES_HOUSE_API_KEY=your_key_here
  5. Completely free, no monthly cost

SIC CODE REFERENCE (key ones for our 4 concepts)
  Concept A (ComplianceWatch — regulated industries):
    64110 — Central banking
    64191 — Banks
    64999 — Financial services
    86210 — General medical practice
    56101 — Restaurants
    41201 — Construction of commercial buildings

  Concept B (LeadPulse — B2B service businesses):
    70221 — Management consulting
    73110 — Advertising agencies
    78109 — Recruitment agencies (other)
    62020 — IT consulting

  Concept C (MetricShield — SME owners):
    47190 — Retail (non-specialised)
    55100 — Hotels
    56290 — Other food service activities

  Concept D (ProcessFlow — operations-heavy):
    52290 — Other activities incidental to transportation
    69101 — Barristers
    69102 — Solicitors
    82990 — Other business support activities

Usage:
    python scripts/source_companies_house.py                  # all SIC profiles
    python scripts/source_companies_house.py --concept A      # ComplianceWatch only
    python scripts/source_companies_house.py --dry-run        # preview
    python scripts/source_companies_house.py --limit 50       # cap results
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from common import (
    LEADS_PATH,
    get_logger,
    load_json,
    load_suppression_set,
    next_concept,
    now_iso,
    save_json,
    today_date,
)

log = get_logger("source_companies_house")

CH_BASE = "https://api.company-information.service.gov.uk"

# SIC codes per concept (maps to concept A/B/C/D)
SIC_PROFILES: dict[str, dict[str, Any]] = {
    "A": {
        "label": "ComplianceWatch",
        "sic_codes": ["64999", "86210", "56101", "41201", "78300", "80200"],
    },
    "B": {
        "label": "LeadPulse",
        "sic_codes": ["70221", "73110", "78109", "62020", "74909"],
    },
    "C": {
        "label": "MetricShield",
        "sic_codes": ["47190", "55100", "56290", "47710", "47730"],
    },
    "D": {
        "label": "ProcessFlow",
        "sic_codes": ["52290", "69102", "82990", "63990", "74100"],
    },
}


def search_companies(api_key: str, sic_code: str, start_index: int = 0) -> dict[str, Any]:
    """Search Companies House for active companies with a given SIC code."""
    resp = requests.get(
        f"{CH_BASE}/search/companies",
        params={
            "q": f"SIC:{sic_code}",
            "items_per_page": 20,
            "start_index": start_index,
        },
        auth=HTTPBasicAuth(api_key, ""),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_officers(api_key: str, company_number: str) -> list[dict[str, Any]]:
    """Return active directors for a company."""
    resp = requests.get(
        f"{CH_BASE}/company/{company_number}/officers",
        params={"items_per_page": 10},
        auth=HTTPBasicAuth(api_key, ""),
        timeout=15,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    officers = data.get("items") or []
    # Keep only active directors (not secretaries, not resigned)
    return [
        o for o in officers
        if o.get("officer_role") in ("director", "managing-director")
        and not o.get("resigned_on")
    ]


def parse_director_name(officer: dict[str, Any]) -> tuple[str, str]:
    """Extract first + last name from a Companies House officer record."""
    name = officer.get("name") or ""
    # Format is usually: "SURNAME, Firstname Middlename"
    parts = name.split(",", 1)
    if len(parts) == 2:
        last = parts[0].strip().capitalize()
        first = parts[1].strip().split()[0].capitalize()
    else:
        words = name.strip().split()
        first = words[0].capitalize() if words else ""
        last = words[-1].capitalize() if len(words) > 1 else ""
    return first, last


def build_website_guess(company_name: str) -> str:
    """Very rough domain guess — Hunter.io will verify it properly."""
    clean = (
        company_name.lower()
        .replace(" limited", "")
        .replace(" ltd", "")
        .replace(" ", "")
        .replace("&", "and")
        .replace("'", "")
    )
    return f"https://www.{clean}.co.uk"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concept", choices=list(SIC_PROFILES.keys()), default=None)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        log.error(
            "COMPANIES_HOUSE_API_KEY not set. "
            "Free key at: developer.company-information.service.gov.uk"
        )
        return 2

    leads_data = load_json(LEADS_PATH) or {
        "metadata": {"total_sourced": 0, "last_concept_index": -1, "concept_counts": {}},
        "leads": [],
    }
    existing_companies = {l["company_name"].lower() for l in leads_data["leads"]}
    suppressed = load_suppression_set()

    profiles = [args.concept] if args.concept else list(SIC_PROFILES.keys())
    new_leads: list[dict[str, Any]] = []

    for concept in profiles:
        if len(new_leads) >= args.limit:
            break
        profile = SIC_PROFILES[concept]
        log.info("Searching Companies House for concept %s (%s)", concept, profile["label"])

        for sic_code in profile["sic_codes"]:
            if len(new_leads) >= args.limit:
                break
            try:
                result = search_companies(api_key, sic_code)
            except requests.HTTPError as e:
                log.warning("CH search failed for SIC %s: %s", sic_code, e)
                time.sleep(1)
                continue

            companies = result.get("items") or []
            log.info("SIC %s: %d companies returned", sic_code, len(companies))

            for company in companies:
                if len(new_leads) >= args.limit:
                    break

                # Only active companies
                if company.get("company_status") != "active":
                    continue

                company_name = company.get("title") or company.get("company_name") or ""
                company_number = company.get("company_number") or ""

                if not company_name or company_name.lower() in existing_companies:
                    continue

                # Get directors
                try:
                    officers = get_officers(api_key, company_number)
                except Exception as e:
                    log.debug("Could not get officers for %s: %s", company_number, e)
                    officers = []
                    time.sleep(0.3)
                    continue

                if not officers:
                    time.sleep(0.3)
                    continue

                # Use the first active director
                director = officers[0]
                first_name, last_name = parse_director_name(director)
                if not first_name:
                    continue

                # We don't have the real website yet — Hunter.io will find it + email
                # Flag with status "needs_email" so source_hunter.py picks it up
                website_guess = build_website_guess(company_name)

                lead = {
                    "id": f"lead_{leads_data['metadata'].get('total_sourced', 0) + len(new_leads) + 1:06d}",
                    "company_name": company_name,
                    "company_number": company_number,
                    "industry": f"SIC:{sic_code}",
                    "country": "GB",
                    "city": (
                        (company.get("registered_office_address") or {}).get("locality") or ""
                    ),
                    "email": "",           # to be filled by source_hunter.py
                    "first_name": first_name,
                    "last_name": last_name,
                    "job_title": "Director",
                    "website": website_guess,
                    "employee_estimate": "5-50",
                    "source": "companies_house",
                    "sourced_date": today_date(),
                    "status": "needs_email",   # trigger Hunter enrichment
                    "concept_assigned": next_concept(leads_data["metadata"]),
                    "emails_sent": 0,
                    "last_email_date": None,
                    "response_status": None,
                    "notes": f"Director: {first_name} {last_name}. Company #{company_number}.",
                }

                new_leads.append(lead)
                existing_companies.add(company_name.lower())
                time.sleep(0.3)   # CH rate limit: ~600 req/min

    log.info("Found %d leads from Companies House (all need Hunter email enrichment)", len(new_leads))

    if args.dry_run:
        for l in new_leads[:5]:
            log.info("DRY-RUN: %s — Director: %s %s", l["company_name"], l["first_name"], l["last_name"])
        return 0

    leads_data["leads"].extend(new_leads)
    leads_data["metadata"]["total_sourced"] = len(leads_data["leads"])
    leads_data["metadata"]["last_source_run"] = now_iso()
    save_json(LEADS_PATH, leads_data)
    log.info("Saved %d Companies House leads. Run source_hunter.py to enrich emails.", len(new_leads))
    return 0


if __name__ == "__main__":
    sys.exit(main())
