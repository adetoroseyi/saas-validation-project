"""Source US leads from People Data Labs (PDL) Person Search API.

Targets named decision-makers at US SMEs (1-200 employees) in industries
relevant to the four validation concepts. Deduplicates against existing
leads.json and suppression list before saving.

PDL free tier: 100 API credits/month (each matched record costs 1 credit).
Script stops as soon as the monthly credit cap is hit (HTTP 402).

Usage:
    python scripts/source_pdl.py                 # default run (up to 100 leads)
    python scripts/source_pdl.py --limit 25      # cap at 25 new leads
    python scripts/source_pdl.py --dry-run       # log only, don't save

Environment variables:
    PDL_API_KEY   required — from https://dashboard.peopledatalabs.com/
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests

from common import (
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

log = get_logger("source_pdl")

PDL_SEARCH_URL = "https://api.peopledatalabs.com/v5/person/search"

# ---------------------------------------------------------------------------
# Search profiles — one per concept, tuned to the decision-maker persona that
# each concept is validated against.
#
# PDL Elasticsearch query reference:
#   https://docs.peopledatalabs.com/docs/person-search-api
#
# job_title_levels accepted values:
#   owner | partner | cxo | vp | director | manager | senior | entry | training
# ---------------------------------------------------------------------------

SEARCH_PROFILES: list[dict[str, Any]] = [
    # --- Concept A: ComplianceWatch ---
    # Finance directors and compliance leads at UK/US regulated SMEs
    {
        "concept_hint": "A",
        "label": "ComplianceWatch — finance/compliance SMEs (US)",
        "query": {
            "bool": {
                "must": [
                    {"term": {"location_country": "united states"}},
                    {"terms": {"job_title_levels": ["cxo", "owner", "partner", "vp", "director"]}},
                    {"terms": {"industry": [
                        "accounting",
                        "financial services",
                        "insurance",
                        "legal services",
                        "management consulting",
                        "staffing and recruiting",
                    ]}},
                ],
                "filter": [
                    {"range": {"job_company_employee_count": {"gte": 5, "lte": 200}}},
                    {"exists": {"field": "work_email"}},
                ],
            }
        },
    },
    # --- Concept B: LeadPulse ---
    # Agency owners, recruiters, IT consultants who struggle with lead tracking
    {
        "concept_hint": "B",
        "label": "LeadPulse — agencies/recruiters/consultants (US)",
        "query": {
            "bool": {
                "must": [
                    {"term": {"location_country": "united states"}},
                    {"terms": {"job_title_levels": ["cxo", "owner", "partner", "vp", "director"]}},
                    {"terms": {"industry": [
                        "marketing and advertising",
                        "staffing and recruiting",
                        "information technology and services",
                        "management consulting",
                        "public relations and communications",
                        "design",
                    ]}},
                ],
                "filter": [
                    {"range": {"job_company_employee_count": {"gte": 2, "lte": 50}}},
                    {"exists": {"field": "work_email"}},
                ],
            }
        },
    },
    # --- Concept C: MetricShield ---
    # SME owners drowning in disconnected tools — retail, hospitality, services
    {
        "concept_hint": "C",
        "label": "MetricShield — SME multi-tool pain (US)",
        "query": {
            "bool": {
                "must": [
                    {"term": {"location_country": "united states"}},
                    {"terms": {"job_title_levels": ["cxo", "owner", "partner"]}},
                    {"terms": {"industry": [
                        "retail",
                        "hospitality",
                        "food & beverages",
                        "health, wellness and fitness",
                        "consumer services",
                        "construction",
                        "real estate",
                    ]}},
                ],
                "filter": [
                    {"range": {"job_company_employee_count": {"gte": 2, "lte": 100}}},
                    {"exists": {"field": "work_email"}},
                ],
            }
        },
    },
    # --- Concept D: ProcessFlow ---
    # Operations / COO / MD at growing SMEs with manual process pain
    {
        "concept_hint": "D",
        "label": "ProcessFlow — operations/manual-process SMEs (US)",
        "query": {
            "bool": {
                "must": [
                    {"term": {"location_country": "united states"}},
                    {"terms": {"job_title_levels": ["cxo", "owner", "partner", "vp", "director"]}},
                    {"bool": {
                        "should": [
                            {"terms": {"job_title_role": ["operations", "founder"]}},
                            {"terms": {"industry": [
                                "logistics and supply chain",
                                "transportation/trucking/railroad",
                                "warehousing",
                                "wholesale",
                                "manufacturing",
                                "facilities services",
                            ]}},
                        ]
                    }},
                ],
                "filter": [
                    {"range": {"job_company_employee_count": {"gte": 5, "lte": 200}}},
                    {"exists": {"field": "work_email"}},
                ],
            }
        },
    },
]

# Requested PDL fields — only what we need (keeps response lean)
PDL_FIELDS = [
    "first_name",
    "last_name",
    "work_email",
    "job_title",
    "job_company_name",
    "job_company_website",
    "job_company_industry",
    "job_company_employee_count",
    "location_name",
    "location_country",
    "location_region",
]


def _employee_bucket(count: int | None) -> str:
    if count is None:
        return "5-20"
    if count >= 100:
        return "100-500"
    if count >= 20:
        return "20-100"
    return "5-20"


def search_pdl(api_key: str, query: dict, size: int = 25) -> list[dict]:
    """Run a PDL person search and return the raw person records.

    Returns an empty list on any non-200 response so callers can continue
    gracefully. Raises on HTTP 402 (credits exhausted) so the caller can stop.
    """
    payload = {
        "query": query,
        "size": size,
        "fields": PDL_FIELDS,
        "pretty": False,
    }
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    resp = requests.post(PDL_SEARCH_URL, json=payload, headers=headers, timeout=30)

    if resp.status_code == 402:
        log.warning("PDL: monthly credit limit reached (HTTP 402) — stopping.")
        raise RuntimeError("PDL credits exhausted")

    if resp.status_code == 401:
        log.error("PDL: invalid API key (HTTP 401). Check PDL_API_KEY in .env.")
        return []

    if resp.status_code != 200:
        log.warning("PDL: unexpected status %s — %s", resp.status_code, resp.text[:300])
        return []

    data = resp.json()
    records = data.get("data") or []
    log.info("PDL: query returned %d records (total_available=%s)", len(records), data.get("total"))
    return records


def extract_lead(record: dict, concept_hint: str) -> dict | None:
    """Map a PDL person record to our lead schema. Returns None if unqualified."""
    email = normalise_email(record.get("work_email") or "")
    if not email or not is_valid_business_email(email):
        return None

    first_name = (record.get("first_name") or "").strip().capitalize()
    last_name  = (record.get("last_name")  or "").strip().capitalize()
    if not first_name:
        return None  # reject anonymous contacts

    company = (record.get("job_company_name") or "").strip()
    website  = (record.get("job_company_website") or "").strip()
    if not company:
        return None

    # Normalise website
    if website and not website.startswith("http"):
        website = "https://" + website

    industry = record.get("job_company_industry") or "Unknown"
    employee_count = record.get("job_company_employee_count")

    city    = record.get("location_name") or ""
    country = (record.get("location_country") or "us").upper()
    if country == "UNITED STATES":
        country = "US"

    return {
        "company_name":      company,
        "industry":          industry,
        "country":           country,
        "city":              city,
        "email":             email,
        "first_name":        first_name,
        "last_name":         last_name,
        "job_title":         (record.get("job_title") or "").strip(),
        "website":           website,
        "employee_estimate": _employee_bucket(employee_count),
        "source":            "pdl",
        "sourced_date":      today_date(),
        "status":            "new",
        "emails_sent":       0,
        "last_email_date":   None,
        "response_status":   None,
        "notes":             "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100,
                        help="Max new leads to add this run (default: 100)")
    parser.add_argument("--per-profile", type=int, default=25,
                        help="PDL records to request per search profile (default: 25)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log results without saving to leads.json")
    args = parser.parse_args()

    api_key = os.getenv("PDL_API_KEY")
    if not api_key:
        log.error("PDL_API_KEY not set. Add it to .env and GitHub Secrets.")
        return 2

    # Load existing state
    leads_data = load_json(LEADS_PATH) or {
        "metadata": {"total_sourced": 0, "last_concept_index": -1, "concept_counts": {}},
        "leads": [],
    }
    existing_emails = {normalise_email(l["email"]) for l in leads_data["leads"]}
    suppressed = load_suppression_set()

    new_leads: list[dict] = []

    try:
        for profile in SEARCH_PROFILES:
            if len(new_leads) >= args.limit:
                break

            log.info("Searching PDL: %s", profile["label"])
            records = search_pdl(api_key, profile["query"], size=args.per_profile)

            added_this_profile = 0
            for record in records:
                if len(new_leads) >= args.limit:
                    break

                lead = extract_lead(record, profile["concept_hint"])
                if not lead:
                    continue

                email = lead["email"]
                if email in existing_emails or email in suppressed:
                    log.debug("Skipping duplicate/suppressed: %s", email)
                    continue

                lead["id"] = (
                    f"lead_{leads_data['metadata'].get('total_sourced', 0) + len(new_leads) + 1:06d}"
                )
                # Concept assignment: honour concept_hint if the round-robin
                # would land on a different letter — nudge by skipping forward.
                # In practice this is just a hint; strict round-robin is fine.
                lead["concept_assigned"] = next_concept(leads_data["metadata"])

                new_leads.append(lead)
                existing_emails.add(email)
                added_this_profile += 1

            log.info("  → %d new leads from this profile", added_this_profile)

    except RuntimeError:
        # PDL credits exhausted — save what we have
        log.info("Saving %d leads collected before credit limit.", len(new_leads))

    log.info("Total new PDL leads this run: %d", len(new_leads))

    if args.dry_run:
        for lead in new_leads[:5]:
            log.info("DRY-RUN sample: %s <%s> at %s (%s)",
                     f"{lead['first_name']} {lead['last_name']}",
                     lead["email"], lead["company_name"], lead["concept_assigned"])
        return 0

    if not new_leads:
        log.info("No new leads to save.")
        return 0

    leads_data["leads"].extend(new_leads)
    leads_data["metadata"]["total_sourced"] = len(leads_data["leads"])
    leads_data["metadata"]["last_pdl_run"] = now_iso()
    save_json(LEADS_PATH, leads_data)
    log.info("Saved. Total leads in database: %d", len(leads_data["leads"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
