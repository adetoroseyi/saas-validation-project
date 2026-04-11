# Concept D — ProcessFlow — Email Sequence

**Concept:** ProcessFlow
**One-liner:** Turn your messy business processes into automated workflows without developers.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 3 touches over 7 days
**Footer (every email):** "Reply 'stop' to opt out."

---

## Email 1 — Day 0 — The Question

**Subject line variants (rotate, A/B test):**
1. manual process question
2. still doing this manually?
3. how much time does {{company_name}} spend on repeat tasks

**Body:**

```
Hi {{first_name}},

There's a point in most growing businesses where the processes work — but only because someone is manually holding them together.

It's usually not one big broken thing. It's five small ones that each eat 20 minutes a day and nobody's ever sat down to fix.

Does {{company_name}} have a process like that — something in onboarding, invoicing, or client handoffs that still runs on human effort because the right tool doesn't quite exist yet?

Early research — genuinely as interested in a 'no' as a 'yes.'

Cheers,
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

To be more specific about what I'm looking into: I'm curious whether {{company_name}} is losing more than five hours a week to tasks that should be automated but aren't.

I grabbed 10 minutes with a logistics firm recently — they're manually copy-pasting from their CRM into a Sage invoice every single afternoon. Same data, three systems, every day. That was their answer to my question. They'd never actually added up how long it was taking before I asked.

If that kind of thing isn't happening at {{company_name}}, no need to reply. But if it is — which specific task would you automate first if you could?

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

Last email from me — I won't keep at it.

I'm trying to decide whether to kill this project or commit to it. The honest input from people actually running operations at businesses like {{company_name}} has been worth more than any market report.

If manual processes aren't slowing things down at {{company_name}}, no need to reply — that's genuinely useful to know.

If they are, one sentence on what your team's most painful manual task is would directly shape what I build.

Either way — best of luck with {{company_name}}.

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
