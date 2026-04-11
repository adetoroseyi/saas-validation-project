# Weekly Reports

Generated every Sunday at 20:00 GMT by `scripts/generate_report.py`.

Each report is named `week_N_report.md` where N = weeks since project start (2026-04-10).

## Report structure

1. **Executive summary** — headline numbers for the week
2. **Concept scorecard** — 10 metrics across all 4 concepts side-by-side
3. **Top feature requests** — what respondents are asking for
4. **Pricing insights** — what respondents said they'd pay
5. **Geographic breakdown** — leads + responses by country
6. **Recommendations** — auto-generated actions based on the data

## When a concept hits validation

If any concept crosses all four validation thresholds, the report flags it and `scripts/generate_report.py` also writes a corresponding build brief to `../06-validated/<concept>_build_brief.md`.

Validation thresholds:
- ≥ 50 interested responses
- ≥ 20 pricing signals above £30/month
- ≥ 10 respondents naming the same top 3 features
- ≥ 5% response rate on 200+ sends

No reports exist yet — the first will appear after Sunday 2026-04-12 (week 1 close).
