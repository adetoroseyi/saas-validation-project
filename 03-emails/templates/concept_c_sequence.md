# Concept C — MetricShield — Email Sequence

**Concept:** MetricShield
**One-liner:** One dashboard that monitors all your business numbers and tells you what needs attention.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 3 touches over 7 days
**Footer (every email):** "Reply 'stop' to opt out."

---

## Email 1 — Day 0 — The Question

**Subject line variants (rotate, A/B test):**
1. too many tabs?
2. dashboard question
3. how many tools are you running

**Body:**

```
Hi {{first_name}},

I've been asking SME owners what their 9:00 AM looks like — it usually involves checking three or four different tabs just to see if the business is on track. By the time they've done the rounds it's already 10am.

I'm looking into whether there's a simpler way to surface the numbers that actually matter, without the daily manual check.

One question: what's the first number you look at every morning to know if {{company_name}} is having a good day or a bad one?

Just doing research — genuinely curious what that looks like in practice.

Thanks,
Sheyi
Founder, T&O Ventures
Sent from my phone

Reply 'stop' to opt out.
```

---

## Email 2 — Day 3 — The Follow-up (only if no reply)

**Subject line:** `Re: {{original_subject}}`

**Body:**

```
Hi {{first_name}},

Brief follow-up.

I grabbed 10 minutes with a retail owner last week — they're pulling numbers from their EPOS, a spreadsheet, and their bank app every morning just to get a basic picture. Said it takes 20 minutes and they still can't tell at a glance whether yesterday actually made money. Their words: "I'm looking at three screens and I'm still guessing."

Curious what that morning check actually looks like at {{company_name}} — and whether you'd describe it as under control.

Cheers,
Sheyi

Reply 'stop' to opt out.
```

---

## Email 3 — Day 7 — The Breakup (only if no reply)

**Subject line:** `Re: {{original_subject}}`

**Body:**

```
Hi {{first_name}},

Last one from me — I won't keep filling your inbox.

I'm trying to decide whether to kill this project or commit to it. The honest feedback from business owners has shaped my thinking more than any industry data.

If keeping track of the numbers isn't a pain at {{company_name}}, no need to reply — that's useful to know.

If it is, one sentence on how you currently stay on top of things would go a long way.

Either way — thanks for your time.

Sheyi

Reply 'stop' to opt out.
```

---

## Template variables

| Variable | Source |
|----------|--------|
| `{{first_name}}` | `leads.json → lead.first_name` (fallback: "there") |
| `{{company_name}}` | `leads.json → lead.company_name` |
| `{{original_subject}}` | `sent_log.json → original send's subject` |

## Rules

- If `first_name` is missing, use "there"
- If `company_name` is missing, skip lead
- Send Email 1 on a weekday 8:00-11:00 AM recipient local time
- Email 2: +72 hours
- Email 3: +168 hours
- Any reply → stop sequence
- Unsubscribe → add to suppression list
