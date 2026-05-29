# Concept D — ProcessFlow — Email Sequence

**Concept:** ProcessFlow
**One-liner:** Turn your messy business processes into automated workflows without developers.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 4 touches over 10 days

---

## Subject Line Variants

**Email 1 (rotate, A/B test):**
1. `still doing this manually?`
2. `the 20-minute task`
3. `{{company_name}} ops question` — fallback if company_name missing: `an ops question`

**Emails 2–4:** `Re: {{original_subject}}`

---

## Email 1 — Day 0

```
Hi {{first_name}},

There's a point in most growing businesses where a process works — but only because one person is manually holding it together.

It's usually not one big broken thing. It's a few small ones that each eat 20 minutes a day, and nobody's fixed them because the workaround technically works.

Does {{company_name}} have something like that — in onboarding, invoicing, or client handoffs?

I'm a founder deciding whether to build something here. Genuinely as useful to hear "we've solved it" as "yes, it's a pain."

Sheyi

Reply 'stop' to opt out.
```

## Email 2 — Day 3

```
Hi {{first_name}},

Different angle on this.

Most people I've spoken to have already tried to fix the manual work problem — usually a spreadsheet that got too complicated, a Zapier flow that half-works, or a VA hired to plug a gap. The fix kind of works, until it doesn't.

Has {{company_name}} gone down any of those roads? I'm curious what you tried and what fell short.

Sheyi

Reply 'stop' to opt out.
```

## Email 3 — Day 7

```
Hi {{first_name}},

One thing I keep hearing.

A logistics firm I spoke to last week manually copies from their CRM into Sage every afternoon. Same data, three systems, every day. When I asked how long it was taking, they'd never actually counted.

Is there a task like that at {{company_name}} — something you've just accepted as part of the job?

Sheyi

Reply 'stop' to opt out.
```

## Email 4 — Day 10

```
Hi {{first_name}},

Last one from me.

I'm deciding this week whether to build this or shelve it. If manual processes aren't actually a pain where you are, that's genuinely useful — it'd point me somewhere else.

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

- Any reply to any email → stop sequence immediately
- Unsubscribe → suppression list, never send again
- Email 2: +72 hours from Email 1
- Email 3: +168 hours from Email 1
- Email 4: +240 hours from Email 1