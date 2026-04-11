# T&O Ventures — SaaS Validation System

Automated lead generation and cold email validation for four SaaS concepts. Runs daily, monitors responses, reports weekly, and flags any concept that crosses the validation threshold.

**Status:** 🟡 Scaffolded — awaiting domain purchase and Workspace setup before live operation.
**Operator:** Sheyi Olu, T&O Ventures Ltd
**Start date:** 2026-04-10

---

## What this system does

1. **Sources leads** from Apify (Google Maps, Website Contacts) — 50–100/day across B2B segments globally
2. **Assigns each lead** to one of four SaaS concepts on round-robin
3. **Sends a 3-touch cold email sequence** over 7 days from a warmed dedicated domain
4. **Monitors replies**, classifies them, and drafts appropriate follow-ups for human review
5. **Generates a weekly report** showing which concept is winning
6. **Produces a build brief** when any concept crosses the validation threshold

The four concepts: **ComplianceWatch**, **LeadPulse**, **MetricShield**, **ProcessFlow**. Full details in [01-concepts/saas_concepts.md](01-concepts/saas_concepts.md).

---

## File map

```
SaaS Validation Project/
├── README.md                                ← you are here
├── .env.example                             ← copy to .env and fill in
├── .gitignore
├── requirements.txt                         ← Python deps
│
├── 00-setup/
│   └── email_domain_guide.md                ← START HERE — domain buy + warmup
│
├── 01-concepts/
│   └── saas_concepts.md                     ← the 4 SaaS ideas being tested
│
├── 02-leads/
│   ├── leads.json                           ← lead database (starts empty)
│   └── suppression_list.json                ← permanent do-not-email list
│
├── 03-emails/
│   ├── templates/
│   │   ├── concept_a_sequence.md            ← ComplianceWatch emails
│   │   ├── concept_b_sequence.md            ← LeadPulse emails
│   │   ├── concept_c_sequence.md            ← MetricShield emails
│   │   └── concept_d_sequence.md            ← ProcessFlow emails
│   └── sent_log.json                        ← every email sent, timestamped
│
├── 04-responses/
│   ├── responses.json                       ← classified incoming replies
│   └── auto_replies/
│       └── reply_templates.md               ← auto-reply templates
│
├── 05-reports/
│   └── week_N_report.md                     ← generated every Sunday 20:00 GMT
│
├── 06-validated/
│   └── [concept]_build_brief.md             ← created when a concept wins
│
└── scripts/
    ├── common.py                            ← shared utilities
    ├── source_leads.py                      ← daily Apify sourcing
    ├── send_emails.py                       ← daily email sending
    ├── monitor_responses.py                 ← response polling + classification
    ├── generate_report.py                   ← weekly reporting
    └── scheduler.py                         ← master entrypoint (cron/GHA)
```

---

## Pre-flight checklist (do these BEFORE any live sending)

1. **Read [00-setup/email_domain_guide.md](00-setup/email_domain_guide.md) end to end.** This is the critical path.
2. Buy domain (suggested: `trysignalbench.com`). Enable WhoisGuard.
3. Set up Google Workspace (Business Starter plan, ~£5/month).
4. Configure SPF, DKIM, DMARC DNS records.
5. Verify domain health at [mxtoolbox.com/emailhealth](https://mxtoolbox.com/emailhealth) and [mail-tester.com](https://mail-tester.com) (aim for 9/10+).
6. Subscribe to Warmbox.ai (~£29 one-off month) and run a 10–14 day warmup.
7. Set up forwarding so replies land in your personal Gmail.
8. Reconnect Gmail MCP in Claude to the new Workspace account.
9. Review email templates in `03-emails/templates/` and adjust tone if needed.
10. Say to Claude: *"Pre-flight is complete. Start Day 1 of live outreach."*

Until step 10, **no emails are sent**.

---

## Running the system

### Mode 1 — Supervised (recommended, inside Claude Code)

Claude Code has Apify, Gmail, and Google Calendar MCPs connected. You run each session interactively:

- *"Source today's leads"* → Claude calls `source_leads.py` (or invokes Apify MCP directly)
- *"Send today's emails"* → Claude reviews the queue, renders templates, sends via Gmail MCP, updates state
- *"Check inbox for replies"* → Claude polls Gmail MCP, classifies, drafts replies for review
- *"Generate this week's report"* → Claude runs `generate_report.py`

This is the default mode during the first 2–3 weeks so you can build trust in the automation.

### Mode 2 — Unattended (GitHub Actions)

Once you trust the system, push it to a private GitHub repo and let GitHub Actions run `scheduler.py` on a cron schedule. Gmail API credentials are stored as GitHub Secrets.

Example `.github/workflows/validation.yml`:

```yaml
name: SaaS Validation
on:
  schedule:
    - cron: "0 7-18 * * 1-5"   # hourly, Mon-Fri, 07:00-18:00 UTC
    - cron: "0 20 * * 0"       # Sunday 20:00 UTC for the weekly report
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python scripts/scheduler.py
        env:
          APIFY_API_TOKEN: ${{ secrets.APIFY_API_TOKEN }}
          GMAIL_TOKEN_JSON: ${{ secrets.GMAIL_TOKEN_JSON }}
          USE_GMAIL_MCP: "0"
      - name: Commit state changes
        run: |
          git config user.name "validation-bot"
          git config user.email "bot@trysignalbench.com"
          git add 02-leads/ 03-emails/ 04-responses/ 05-reports/ 06-validated/
          git diff --staged --quiet || git commit -m "daily state update"
          git push
```

---

## Daily schedule (when live)

| GMT Time | Task |
|---|---|
| 07:00 Mon-Fri | Source new leads |
| 08:00 Mon-Fri | Send Email 1s to new leads |
| 08:30 Mon-Fri | Send Email 2s (Day 3 follow-ups) |
| 09:00 Mon-Fri | Send Email 3s (Day 7 breakups) |
| 10:00 / 12:00 / 14:00 / 16:00 / 18:00 Mon-Fri | Monitor inbox, classify, draft replies |
| 20:00 Sunday | Generate weekly report |

**Caps during warm-up weeks:** 25 emails/day for the first 2 weeks, then 50/day, then 80/day.

---

## Cost summary

| Item | Cost | Notes |
|---|---|---|
| Domain (`trysignalbench.com`) | ~£25/year | Namecheap or Porkbun |
| Google Workspace Business Starter | ~£5/month | Required for Gmail MCP |
| Warmbox.ai | ~£29 (one month) | Skip after warmup complete |
| Apify usage | ~£25–40/month | Based on 1500–2500 leads/month |
| **Month 1 total** | **~£84** | |
| **Ongoing monthly** | **~£30–45** | |

---

## Key safety rules

1. **Never send from `olubusinessempire@gmail.com`** — personal account protection is non-negotiable.
2. **Never skip warmup.** A cold domain + 80 cold emails = blacklist within 48 hours.
3. **Honour every unsubscribe immediately.** The suppression list is append-only; never removed from.
4. **Auto-replies are drafts only** until 200+ replies have been classified manually and accuracy confirmed above 95%. Drafts are reviewed by a human before sending.
5. **No email to `info@`, `contact@`, `support@` or personal-provider addresses** — `is_valid_business_email()` in `scripts/common.py` enforces this.
6. **Weekend rule:** no sending Saturday or Sunday, anywhere, ever.

---

## Validation thresholds (when does a concept "win"?)

A concept is flagged `VALIDATED — Ready to Build` when ALL of these are true:

- ≥ 50 interested responses
- ≥ 20 pricing signals quoting more than £30/month
- ≥ 10 respondents mentioning the same top-3 features
- Response rate ≥ 5% on 200+ sends

At that point, `scripts/generate_report.py` auto-writes `06-validated/<concept>_build_brief.md`.

---

## Next actions for Sheyi (in order)

1. [ ] Work through [00-setup/email_domain_guide.md](00-setup/email_domain_guide.md). Allow ~2 days elapsed time for DNS propagation.
2. [ ] Start Warmbox warmup, let it run 10–14 days.
3. [ ] While warmup is running, review and adjust:
    - [01-concepts/saas_concepts.md](01-concepts/saas_concepts.md) — are the 4 concepts right?
    - [03-emails/templates/](03-emails/templates/) — does the tone sound like you?
4. [ ] After warmup, reconnect Gmail MCP to `sheyi@trysignalbench.com` in Claude.
5. [ ] Tell Claude: *"Pre-flight is complete. Start Day 1 of live outreach."*
6. [ ] Claude runs controlled-volume Day 1 (25 emails), reviews with you, then proceeds.

---

## Troubleshooting

- **"mail-tester score under 8"** → fix the flagged DNS record, don't start warmup until 9/10+
- **"Gmail MCP still on olubusinessempire"** → Settings → Connectors → disconnect → reconnect with new account
- **"Apify is burning through credit too fast"** → reduce `maxCrawledPlacesPerSearch` in `source_leads.py` or cut the number of queries per day
- **"Responses are being misclassified"** → rules live in `scripts/monitor_responses.py`. Add regex patterns and test with `python scripts/monitor_responses.py --classify-only < sample.txt`
