# Concept C — MetricShield — Email Sequence

**Concept:** MetricShield
**One-liner:** One view of all your business numbers, without the daily tab safari.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 4 touches over 10 days

---

## Subject Line Variants

**Email 1 (rotate, A/B test):**
1. `too many tabs?`
2. `the 9am check`
3. `how many tools does {{company_name}} run` — fallback: `how many tools are you running`

**Emails 2–4:** `Re: {{original_subject}}`

---

## Email 1 — Day 0

```
Hi {{first_name}},

I've been asking SME owners what their 9:00 AM looks like — it usually involves checking three or four different tabs just to see if the business is on track. By the time they've done the rounds it's already 10am.

I'm looking into whether there's a simpler way to surface the numbers that actually matter, without the daily manual check.

One question: what's the first number you look at every morning to know if {{company_name}} is having a good day or a bad one?

I'm a founder deciding whether to build something here. Genuinely as useful to hear "we've solved this" as "yes, it's a pain."

Sheyi

Reply 'stop' to opt out.
```

## Email 2 — Day 3

```
Hi {{first_name}},

Different angle on this.

Most business owners I've spoken to have already tried to fix the morning check problem — a Power BI dashboard nobody quite finished, a spreadsheet that pulls from three places but breaks when something changes, a weekly report someone sends manually. The fix kind of works, until it doesn't.

Has {{company_name}} gone down any of those roads? Curious what you tried and what fell short.

Sheyi

Reply 'stop' to opt out.
```

## Email 3 — Day 7

```
Hi {{first_name}},

One thing I keep hearing.

A retail owner I spoke to last week pulls numbers from their EPOS, a spreadsheet, and their bank app every morning just to get a basic picture. Said it takes 20 minutes and they still can't tell at a glance whether yesterday actually made money. Their words: "I'm looking at three screens and I'm still guessing."

Is yours under control, or still a patchwork?

Sheyi

Reply 'stop' to opt out.
```

## Email 4 — Day 10

```
Hi {{first_name}},

Last one from me.

I'm deciding this week whether to build something here or shelve it. If keeping track of the numbers isn't actually a pain at {{company_name}}, that's genuinely useful — it'd point me somewhere else.

Either way, thanks for your time.

Sheyi

Reply 'stop' to opt out.
```

---

## Template Variables

- `{{first_name}}` — fallback: omit greeting, start body directly
- `{{company_name}}` — fallback: "your business"
- `{{original_subject}}` — from sent_log.json first send subject

## Rules

- Any reply → stop sequence
- Unsubscribe → suppression list
- Email 2: +72h, Email 3: +168h, Email 4: +240h