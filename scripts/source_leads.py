"""Source new leads from Apify's Google Maps Scraper.

Runs once per day (scheduled via scheduler.py or GitHub Actions). Reads
a pool of search queries from the constants below, runs the Apify actor,
extracts qualified leads, deduplicates against existing leads.json, and
assigns each new lead to a concept via round-robin rotation.

Usage:
    python scripts/source_leads.py                # default daily run
    python scripts/source_leads.py --queries 3    # limit to 3 queries
    python scripts/source_leads.py --dry-run      # log only, don't save

Environment variables:
    APIFY_API_TOKEN           required
    APIFY_GOOGLE_MAPS_ACTOR   default: compass/crawler-google-places
    DAILY_LEAD_TARGET         default: 75
"""

from __future__ import annotations

import argparse
import os
import sys
import time
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

log = get_logger("source_leads")

APIFY_BASE = "https://api.apify.com/v2"
DEFAULT_ACTOR = "compass/crawler-google-places"

# Rotation pool. Each scheduled run picks N queries from this list.
# Rotate through segments over the project lifetime (see saas_concepts.md
# for the expansion schedule).
SEARCH_POOL = [
    # English-speaking markets (weeks 1-2)
    {"search": "marketing agency", "location": "Manchester, UK"},
    {"search": "marketing agency", "location": "Austin, Texas, USA"},
    {"search": "marketing agency", "location": "Melbourne, Australia"},
    {"search": "accounting firm", "location": "Birmingham, UK"},
    {"search": "accounting firm", "location": "Toronto, Canada"},
    {"search": "recruitment agency", "location": "London, UK"},
    {"search": "recruitment agency", "location": "Sydney, Australia"},
    {"search": "construction company", "location": "Leeds, UK"},
    {"search": "construction company", "location": "Denver, Colorado, USA"},
    {"search": "IT services", "location": "Dublin, Ireland"},
    {"search": "IT services", "location": "Edinburgh, UK"},
    {"search": "logistics company", "location": "Rotterdam, Netherlands"},
    {"search": "property management", "location": "Miami, Florida, USA"},
    {"search": "law firm", "location": "Bristol, UK"},
    # Europe (weeks 3-4)
    {"search": "marketing agentur", "location": "Berlin, Germany"},
    {"search": "recruitment", "location": "Amsterdam, Netherlands"},
    {"search": "consulting firm", "location": "Stockholm, Sweden"},
    # Global (week 5+)
    {"search": "marketing agency", "location": "Dubai, UAE"},
    {"search": "IT services", "location": "Singapore"},
    {"search": "consulting firm", "location": "Bangalore, India"},
]


def run_actor(actor_id: str, token: str, input_payload: dict[str, Any]) -> str:
    """Start an Apify actor run and block until it finishes. Returns datasetId."""
    url = f"{APIFY_BASE}/acts/{actor_id.replace('/', '~')}/run-sync-get-dataset-items"
    params = {"token": token, "format": "json"}
    log.info("Starting actor %s with payload: %s", actor_id, input_payload)
    resp = requests.post(url, params=params, json=input_payload, timeout=600)
    resp.raise_for_status()
    # run-sync-get-dataset-items returns the items directly as an array
    return resp.json()


def extract_lead(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map an Apify Google Maps item to our lead schema. Returns None if unqualified.

    Priority order for contacts:
      1. LinkedIn-enriched lead (leadsEnrichment) — named person with verified work email
      2. Website-scraped personal email (firstname.lastname@ pattern)
      3. Reject — generic inbox or no email found
    """
    company = item.get("title") or item.get("name")
    website = item.get("website") or item.get("webSite")
    if not company or not website:
        return None

    email = None
    first_name = None
    last_name = None
    job_title = None

    # Priority 1: LinkedIn enrichment (named contact with verified work email)
    enriched = item.get("leadsEnrichment") or []
    for contact in enriched:
        candidate = normalise_email(contact.get("email") or "")
        if is_valid_business_email(candidate):
            email = candidate
            first_name = (contact.get("firstName") or "").strip().capitalize()
            last_name = (contact.get("lastName") or "").strip().capitalize()
            job_title = contact.get("jobTitle") or ""
            break

    # Priority 2: Website-scraped emails — accept only if they look personal (name.surname@)
    if not email:
        for raw in item.get("emails") or []:
            candidate = normalise_email(raw)
            if not is_valid_business_email(candidate):
                continue
            local = candidate.split("@", 1)[0]
            # Accept if local part contains a dot (e.g. hayley.perez) — looks like a real person
            if "." in local and "_" not in local:
                email = candidate
                first_name = local.split(".")[0].capitalize()
                last_name = local.split(".")[1].capitalize() if len(local.split(".")) > 1 else ""
                break

    if not email:
        return None

    # Fallback first name from email if enrichment didn't supply one
    if not first_name:
        local = email.split("@", 1)[0]
        first_name = local.split(".")[0].capitalize()

    # Estimate employee count from review volume (proxy)
    categories = " ".join(item.get("categories") or [])
    reviews_count = item.get("reviewsCount") or 0
    if reviews_count > 500:
        employee_estimate = "100-500"
    elif reviews_count > 100:
        employee_estimate = "20-100"
    else:
        employee_estimate = "5-20"

    source_label = "google_maps_linkedin" if job_title else "google_maps_apify"

    return {
        "company_name": company,
        "industry": categories or "Unknown",
        "country": item.get("countryCode") or "",
        "city": item.get("city") or "",
        "email": email,
        "first_name": first_name,
        "last_name": last_name or "",
        "job_title": job_title or "",
        "website": website,
        "employee_estimate": employee_estimate,
        "source": source_label,
        "sourced_date": today_date(),
        "status": "new",
        "emails_sent": 0,
        "last_email_date": None,
        "response_status": None,
        "notes": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=int, default=5, help="Number of queries to run")
    parser.add_argument("--max-per-query", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        log.error("APIFY_API_TOKEN not set. See .env.example.")
        return 2

    actor_id = os.getenv("APIFY_GOOGLE_MAPS_ACTOR", DEFAULT_ACTOR)
    daily_target = int(os.getenv("DAILY_LEAD_TARGET", "75"))

    # Load existing state
    leads_data = load_json(LEADS_PATH) or {
        "metadata": {"total_sourced": 0, "last_concept_index": -1, "concept_counts": {}},
        "leads": [],
    }
    existing_emails = {normalise_email(l["email"]) for l in leads_data["leads"]}
    suppressed = load_suppression_set()

    # Pick queries for this run — simple rotation based on day-of-year
    day_seed = int(time.strftime("%j")) if not args.dry_run else 0
    queries = [SEARCH_POOL[(day_seed + i) % len(SEARCH_POOL)] for i in range(args.queries)]
    log.info("Today's queries: %s", queries)

    new_leads: list[dict[str, Any]] = []
    for q in queries:
        if len(new_leads) >= daily_target:
            log.info("Hit daily target of %d — stopping", daily_target)
            break
        payload = {
            "searchStringsArray": [q["search"]],
            "locationQuery": q["location"],
            "maxCrawledPlacesPerSearch": args.max_per_query,
            "language": "en",
            "website": "withWebsite",       # only businesses with a website
            "skipClosedPlaces": True,
            "scrapeContacts": True,         # extract emails from company website
            "maximumLeadsEnrichmentRecords": 1,  # LinkedIn enrichment: 1 named contact per company
            "leadsEnrichmentDepartments": [     # target decision-makers only
                "c_suite",
                "operations",
                "marketing",
                "sales",
            ],
            "scrapePlaceDetailPage": False,  # skip — saves cost, not needed for leads
            "maxReviews": 0,
            "maxImages": 0,
        }
        try:
            items = run_actor(actor_id, token, payload)
        except requests.HTTPError as e:
            log.error("Apify call failed for query %s: %s", q, e)
            continue

        for item in items:
            lead = extract_lead(item)
            if not lead:
                continue
            if lead["email"] in existing_emails or lead["email"] in suppressed:
                continue
            lead["id"] = f"lead_{leads_data['metadata'].get('total_sourced', 0) + len(new_leads) + 1:06d}"
            lead["concept_assigned"] = next_concept(leads_data["metadata"])
            new_leads.append(lead)
            existing_emails.add(lead["email"])
            if len(new_leads) >= daily_target:
                break

    log.info("Sourced %d new qualified leads", len(new_leads))

    if args.dry_run:
        for l in new_leads[:5]:
            log.info("DRY-RUN sample lead: %s", l)
        return 0

    leads_data["leads"].extend(new_leads)
    leads_data["metadata"]["total_sourced"] = len(leads_data["leads"])
    leads_data["metadata"]["last_source_run"] = now_iso()
    save_json(LEADS_PATH, leads_data)
    log.info("Saved. Total leads in database: %d", len(leads_data["leads"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
