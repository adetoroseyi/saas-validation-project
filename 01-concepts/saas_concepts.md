# SaaS Concepts to Validate

**Project start:** 2026-04-10
**Validation operator:** Sheyi Olu, T&O Ventures Ltd
**Method:** Cold email outreach → conversation → interest/pricing/feature signals
**Success threshold per concept:** 50+ interested responses, 20+ pricing signals above £30/month, 10+ respondents naming the same top 3 features, response rate above 5%

These four concepts are what we're testing. Each lead is assigned one concept on a round-robin (A, B, C, D, A, B, C, D...) so we get comparable sample sizes.

---

## Concept A — ComplianceWatch

| | |
|---|---|
| **One-liner** | Automated compliance monitoring that alerts you before violations happen. |
| **Category** | RegTech / Risk |
| **Target industries** | Finance, healthcare, food service, construction, HR, legal services, manufacturing |
| **Target company size** | 10-500 employees |
| **Target role** | Compliance manager, COO, owner, head of operations |
| **Core pain** | Regulatory requirements are scattered, constantly changing, and mostly tracked manually or by expensive consultants. Violations are discovered after the fact. |
| **Value prop** | Stop paying consultants to check what software can check automatically. Get alerted before a requirement becomes a violation. |
| **Price test points** | £49/month, £99/month, £199/month |
| **Key risk** | Compliance is industry-specific — "general compliance" tools historically struggle. May need vertical focus. |
| **Questions to validate in replies** | How do you track compliance today? What does it cost you? Have you had a near-miss or actual violation? Would you pay £99/month for automated monitoring? |

### Subject line variants (Email 1)
- Quick question about [company_name]
- [first_name], curious about something
- How [company_name] handles compliance tracking

---

## Concept B — LeadPulse

| | |
|---|---|
| **One-liner** | See exactly which companies are looking for your services right now. |
| **Category** | Sales Intelligence |
| **Target industries** | Marketing agencies, consultancies, freelancers, contractors, recruitment, B2B service businesses |
| **Target company size** | 2-100 employees |
| **Target role** | Founder, head of growth, head of sales, business development |
| **Core pain** | Cold outreach is expensive and low-converting. Buying lead lists is inaccurate. Paid ads get more expensive every quarter. Referrals don't scale. |
| **Value prop** | Stop guessing who to pitch. Get a daily list of companies showing buying signals (hiring, funding, tech stack changes, job ads, news mentions). |
| **Price test points** | £29/month, £79/month, £149/month |
| **Key risk** | Crowded space (ZoomInfo, Apollo, Clay). Differentiation has to be intent signals + price. |
| **Questions to validate in replies** | How do you currently find new clients? What % come from referrals vs outbound? What do you pay for leads today? Would you pay £79/month for a daily warm-leads list? |

### Subject line variants (Email 1)
- How does [company_name] find new clients?
- [first_name], quick question about lead gen
- A thought on [company_name]'s growth

---

## Concept C — MetricShield

| | |
|---|---|
| **One-liner** | One dashboard that monitors all your business numbers and tells you what needs attention. |
| **Category** | Business Intelligence / Alerting |
| **Target industries** | SME across all sectors — retail, services, ecommerce, hospitality, manufacturing |
| **Target company size** | 10-500 employees |
| **Target role** | Owner, operations manager, finance lead, general manager |
| **Core pain** | Data lives in 6+ tools (Xero, Shopify, Google Analytics, spreadsheets, CRM, bank, inventory system). Owners check each one daily to spot problems. Most days nothing changes — so the checking becomes noise. |
| **Value prop** | Stop checking 6 different tools every morning. Get one alert when something actually matters. |
| **Price test points** | £39/month, £99/month, £199/month |
| **Key risk** | "Unified dashboard" is a graveyard of failed startups. Differentiation must be **proactive alerting with smart thresholds**, not another dashboard. |
| **Questions to validate in replies** | How many tools do you check daily? What would you pay to have problems flagged instead of checking? Would you pay £99/month for proactive alerts? |

### Subject line variants (Email 1)
- [first_name], quick question about tracking metrics
- How [company_name] stays on top of the numbers
- A question about your daily dashboard routine

---

## Concept D — ProcessFlow

| | |
|---|---|
| **One-liner** | Turn your messy business processes into automated workflows without developers. |
| **Category** | Workflow Automation / No-code |
| **Target industries** | Operations-heavy industries — logistics, professional services, agencies, healthcare admin, legal admin, real estate |
| **Target company size** | 20-500 employees |
| **Target role** | Operations manager, COO, head of admin, process lead |
| **Core pain** | Recurring manual processes (client onboarding, invoicing chase, reporting, data entry) eat 20%+ of team time. Zapier is too fiddly, full automation platforms (Workato, Make) are overkill and developer-heavy. |
| **Value prop** | If your team follows steps in a spreadsheet or document, this replaces it with automation. No developers needed. |
| **Price test points** | £59/month, £129/month, £249/month |
| **Key risk** | Competes with Zapier, Make, n8n. Differentiator must be "describe your process in English, get a workflow" — LLM-native, not drag-and-drop. |
| **Questions to validate in replies** | What manual process eats the most team time right now? Have you tried Zapier/Make? Why didn't it stick? Would you pay £129/month for an English-in, automation-out tool? |

### Subject line variants (Email 1)
- Quick question for [company_name]
- [first_name], a thought on manual processes
- How much time does [company_name] spend on repeat tasks?

---

## Concept assignment rules

1. Every new lead sourced by `scripts/source_leads.py` is assigned ONE concept in strict round-robin order: A → B → C → D → A → ...
2. Assignment is tracked by incrementing a counter in `02-leads/leads.json` metadata (`last_concept_index`).
3. A lead never receives emails for more than one concept.
4. If a lead replies, ALL future sends to them are stopped, regardless of concept.
5. Concept assignment is final — we don't re-test a lead on a different concept even after they say "not interested" to the first.

## Cross-concept signals we still capture

Even though each lead is tested on one concept, weekly reports capture cross-concept signals:

- **Shared pain points** — if respondents to Concept A keep bringing up metric-tracking problems, that's a vote for Concept C
- **Feature crossover requests** — e.g. someone on LeadPulse asking "can it also monitor compliance deadlines?" suggests A+B integration potential
- **Unexpected enthusiasm** — if one concept has a massively higher reply rate, we increase its share in subsequent sourcing

## Kill criteria (per concept)

A concept is paused when:
- Under 1% reply rate after 200+ sends, OR
- Zero pricing signals above £30/month after 20+ interested responses, OR
- Consistent "we don't have this problem" responses from 15+ replies in the target ICP
