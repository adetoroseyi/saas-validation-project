"""Generate the weekly SaaS validation report.

Runs every Sunday at 20:00 GMT. Reads leads.json, sent_log.json, and
responses.json; computes per-concept metrics and writes a Markdown
report to 05-reports/week_N_report.md. Also checks validation thresholds
and produces a build brief in 06-validated/ if any concept wins.

Usage:
    python scripts/generate_report.py             # run for current week
    python scripts/generate_report.py --week 3    # force a specific week
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from common import (
    CONCEPT_NAMES,
    CONCEPTS,
    LEADS_PATH,
    REPORTS_DIR,
    RESPONSES_PATH,
    SENT_LOG_PATH,
    VALIDATED_DIR,
    get_logger,
    load_json,
    save_json,
    today_date,
)

log = get_logger("generate_report")

PROJECT_START = date(2026, 4, 10)

# Validation thresholds — any concept hitting ALL of these is flagged VALIDATED
VALIDATION_THRESHOLDS = {
    "interested_count": 50,
    "pricing_signals_above_30": 20,
    "feature_consensus_count": 10,
    "response_rate_pct": 5.0,
}


def week_number(today: date | None = None) -> int:
    today = today or date.today()
    return max(1, ((today - PROJECT_START).days // 7) + 1)


def week_range(week_num: int) -> tuple[date, date]:
    start = PROJECT_START + timedelta(days=(week_num - 1) * 7)
    end = start + timedelta(days=6)
    return start, end


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def in_week(ts: str, start: date, end: date) -> bool:
    try:
        d = parse_iso(ts).date()
    except (ValueError, AttributeError):
        return False
    return start <= d <= end


def compute_concept_metrics(
    leads: list[dict[str, Any]],
    sends: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    start: date,
    end: date,
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {
        c: {
            "leads_contacted": 0,
            "emails_sent": 0,
            "responses": 0,
            "interested": 0,
            "pricing_questions": 0,
            "not_interested": 0,
            "unsubscribes": 0,
            "auto_replies": 0,
            "questions": 0,
            "pricing_signals": [],
            "feature_requests": [],
        }
        for c in CONCEPTS
    }

    # Leads contacted this week
    for lead in leads:
        if lead.get("last_email_date") and in_week(lead["last_email_date"], start, end):
            concept = lead.get("concept_assigned")
            if concept in metrics:
                metrics[concept]["leads_contacted"] += 1

    # Emails sent this week
    for send in sends:
        if in_week(send["sent_at"], start, end):
            concept = send.get("concept")
            if concept in metrics:
                metrics[concept]["emails_sent"] += 1

    # Responses this week
    for resp in responses:
        if in_week(resp.get("received_date", ""), start, end):
            concept = resp.get("concept")
            if concept not in metrics:
                continue
            metrics[concept]["responses"] += 1
            cls = resp.get("classification", "")
            key = {
                "interested": "interested",
                "pricing_question": "pricing_questions",
                "not_interested": "not_interested",
                "unsubscribe": "unsubscribes",
                "auto_reply": "auto_replies",
                "question": "questions",
            }.get(cls)
            if key:
                metrics[concept][key] += 1
            if resp.get("pricing_signal"):
                metrics[concept]["pricing_signals"].append(resp["pricing_signal"])
            for feat in resp.get("feature_requests") or []:
                metrics[concept]["feature_requests"].append(feat)

    for c in CONCEPTS:
        sent = metrics[c]["emails_sent"]
        metrics[c]["response_rate_pct"] = (
            round(100 * metrics[c]["responses"] / sent, 1) if sent else 0.0
        )
    return metrics


def geo_breakdown(leads, responses, start, end) -> list[dict[str, Any]]:
    per_country: dict[str, dict[str, int]] = defaultdict(lambda: {"leads": 0, "responses": 0})
    for lead in leads:
        country = lead.get("country") or "unknown"
        per_country[country]["leads"] += 1
    resp_emails = {r["email"] for r in responses if in_week(r.get("received_date", ""), start, end)}
    for lead in leads:
        if lead["email"] in resp_emails:
            country = lead.get("country") or "unknown"
            per_country[country]["responses"] += 1
    return [
        {"country": c, **v, "rate": round(100 * v["responses"] / v["leads"], 1) if v["leads"] else 0}
        for c, v in sorted(per_country.items(), key=lambda x: -x[1]["leads"])
    ]


def check_validation(metrics: dict[str, dict[str, Any]]) -> list[str]:
    winners = []
    for concept, m in metrics.items():
        # All-time cumulative counts — caller passes all_time_metrics, not weekly.
        interested = m["interested"]
        pricing_signals = len(m["pricing_signals"])
        feat_counts = Counter(m["feature_requests"])
        consensus = sum(1 for _, count in feat_counts.most_common(3) if count >= 3)
        rate = m["response_rate_pct"]

        if (
            interested >= VALIDATION_THRESHOLDS["interested_count"]
            and pricing_signals >= VALIDATION_THRESHOLDS["pricing_signals_above_30"]
            and consensus >= 3
            and rate >= VALIDATION_THRESHOLDS["response_rate_pct"]
        ):
            winners.append(concept)
    return winners


def render_report(
    week_num: int,
    start: date,
    end: date,
    totals: dict[str, int],
    metrics: dict[str, dict[str, Any]],
    geo: list[dict[str, Any]],
    winners: list[str],
) -> str:
    lines = [
        f"# Weekly SaaS Validation Report — Week {week_num}",
        f"## {start.isoformat()} to {end.isoformat()}",
        "",
        "### Executive Summary",
        f"- Total leads sourced this week: {totals['leads_sourced']}",
        f"- Total emails sent: {totals['emails_sent']}",
        f"- Total responses received: {totals['responses']}",
        f"- Overall response rate: {totals['response_rate_pct']}%",
        f"- Winning concept so far: {', '.join(winners) if winners else 'None yet'}",
        "",
        "### Concept Scorecard",
        "",
        "| Metric | ComplianceWatch (A) | LeadPulse (B) | MetricShield (C) | ProcessFlow (D) |",
        "|---|---|---|---|---|",
    ]
    rows = [
        ("Leads contacted", "leads_contacted"),
        ("Emails sent", "emails_sent"),
        ("Responses", "responses"),
        ("Response rate (%)", "response_rate_pct"),
        ("Interested", "interested"),
        ("Pricing questions", "pricing_questions"),
        ("Not interested", "not_interested"),
        ("Unsubscribes", "unsubscribes"),
        ("Auto-replies", "auto_replies"),
        ("Open questions", "questions"),
    ]
    for label, key in rows:
        row = f"| {label} |"
        for c in CONCEPTS:
            row += f" {metrics[c][key]} |"
        lines.append(row)
    lines.append("")

    # Feature request summary
    lines.append("### Top Feature Requests (all concepts)")
    all_features: list[str] = []
    for c in CONCEPTS:
        all_features.extend(metrics[c]["feature_requests"])
    if all_features:
        for feat, count in Counter(all_features).most_common(10):
            lines.append(f"- {feat} — {count}")
    else:
        lines.append("- None reported yet")
    lines.append("")

    # Pricing insights
    lines.append("### Pricing Insights")
    all_prices: list[str] = []
    for c in CONCEPTS:
        all_prices.extend(metrics[c]["pricing_signals"])
    if all_prices:
        for p in all_prices[:15]:
            lines.append(f"- {p}")
    else:
        lines.append("- No pricing signals yet")
    lines.append("")

    # Geography
    lines.append("### Geographic Breakdown")
    lines.append("| Country | Leads | Responses | Rate |")
    lines.append("|---|---|---|---|")
    for g in geo[:20]:
        lines.append(f"| {g['country']} | {g['leads']} | {g['responses']} | {g['rate']}% |")
    lines.append("")

    # Recommendations
    lines.append("### Recommendations")
    if winners:
        for c in winners:
            lines.append(f"- **{c} ({CONCEPT_NAMES[c]}) VALIDATED** — generate build brief in 06-validated/")
    else:
        lowest = min(CONCEPTS, key=lambda c: metrics[c]["response_rate_pct"] if metrics[c]["emails_sent"] > 10 else 999)
        highest = max(CONCEPTS, key=lambda c: metrics[c]["response_rate_pct"])
        if metrics[lowest]["emails_sent"] > 50 and metrics[lowest]["response_rate_pct"] < 1:
            lines.append(f"- Consider pausing Concept {lowest} — response rate below 1% after 50+ sends")
        if metrics[highest]["response_rate_pct"] > 3:
            lines.append(f"- Concept {highest} is performing best — increase its share in next week's sourcing")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, default=None)
    args = parser.parse_args()

    leads_data = load_json(LEADS_PATH)
    sent_data = load_json(SENT_LOG_PATH)
    resp_data = load_json(RESPONSES_PATH)

    leads = leads_data.get("leads", [])
    sends = sent_data.get("sends", [])
    responses = resp_data.get("responses", [])

    wk = args.week or week_number()
    start, end = week_range(wk)
    log.info("Generating report for week %d (%s to %s)", wk, start, end)

    # Totals for the week
    leads_sourced = sum(1 for l in leads if l.get("sourced_date") and start.isoformat() <= l["sourced_date"] <= end.isoformat())
    emails_this_week = sum(1 for s in sends if in_week(s["sent_at"], start, end))
    responses_this_week = sum(1 for r in responses if in_week(r.get("received_date", ""), start, end))
    totals = {
        "leads_sourced": leads_sourced,
        "emails_sent": emails_this_week,
        "responses": responses_this_week,
        "response_rate_pct": round(100 * responses_this_week / emails_this_week, 1) if emails_this_week else 0.0,
    }

    metrics = compute_concept_metrics(leads, sends, responses, start, end)
    # Validation checks use all-time cumulative data, not just this week
    all_time_start = date(2020, 1, 1)
    all_time_metrics = compute_concept_metrics(leads, sends, responses, all_time_start, end)
    geo = geo_breakdown(leads, responses, start, end)
    winners = check_validation(all_time_metrics)

    report = render_report(wk, start, end, totals, metrics, geo, winners)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"week_{wk}_report.md"
    out.write_text(report, encoding="utf-8")
    log.info("Report written to %s", out)

    # If any concept validated, produce a build brief
    for concept in winners:
        brief_path = VALIDATED_DIR / f"{CONCEPT_NAMES[concept].lower()}_build_brief.md"
        VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
        brief_path.write_text(
            f"# Build Brief: {CONCEPT_NAMES[concept]}\n\n"
            f"**Validated on:** {today_date()}\n"
            f"**Week:** {wk}\n\n"
            f"This concept has crossed all validation thresholds. "
            f"Review the responses tagged with concept {concept} in "
            f"04-responses/responses.json and extract:\n\n"
            "1. **Problem statement** from interested responses\n"
            "2. **Must-have features** from the top-3 feature requests\n"
            "3. **Pricing model** from pricing signals\n"
            "4. **First 10 customers** — the most enthusiastic responders\n"
            "5. **Competitors mentioned** by responders\n\n"
            "Human review required before any build work starts.\n",
            encoding="utf-8",
        )
        log.info("Build brief written: %s", brief_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
