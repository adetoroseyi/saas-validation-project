# Validated Concepts — Build Briefs

This folder holds build briefs for SaaS concepts that have crossed the validation threshold during the cold-outreach experiment.

A concept is "validated" when:

- ≥ 50 interested responses have been logged
- ≥ 20 pricing signals above £30/month have been captured
- ≥ 10 respondents have mentioned the same top 3 features
- The response rate is above 5% on at least 200 sends

When `scripts/generate_report.py` detects that any concept has crossed all four thresholds, it auto-writes a skeleton `<concept_name>_build_brief.md` in this folder. The brief lists:

1. The validated problem (synthesised from interested responses)
2. Target customer profile (industry, company size, role)
3. Must-have features (from top feature requests)
4. Pricing model (from willingness-to-pay signals)
5. First 10 customers (the most enthusiastic responders, as outreach targets for beta)
6. Competitive landscape (competitors mentioned in responses)

**Human review is required before any code is written for a validated concept.** The system surfaces data; the founder makes the call.

No briefs exist yet — this folder will fill up as concepts cross the threshold.
