# Concept B — LeadPulse — Email Sequence

**Concept:** LeadPulse
**One-liner:** See exactly which companies are looking for your services right now.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 4 touches over 10 days

---

## Subject Line Variants

**Email 1 (rotate, A/B test):**
1. `how does {{company_name}} find new work`
2. `question re: referral process`
3. `{{company_name}} pipeline question` — fallback: `pipeline question`

**Emails 2–4:** `Re: {{original_subject}}`

---

## Email 1 — Day 0

```
Hi {{first_name}},

Most {{industry_peer}}s I've spoken to say the same thing — referrals keep the lights on, but they can't tell you when the next one's coming.

I'm looking into whether there's a better way to spot businesses that are actively looking for services like yours — before they've posted a brief or gone to a competitor.

One honest question: where does most of {{company_name}}'s new work actually come from — is it mostly word of mouth, or are you running active outbound?

I'm a founder deciding whether to build something here. Genuinely as useful to hear "we've solved this" as "yes, it's a real problem."

Sheyi

Reply 'stop' to opt out.
```

## Email 2 — Day 3

```
Hi {{first_name}},

Different angle on this.

Most {{industry_peer}}s I've spoken to have already tried to get ahead of the pipeline problem — LinkedIn outreach, a referral scheme, a part-time BD person. Something usually sticks for a few months, then it drifts back.

What's {{company_name}} tried on this front, and what did or didn't work?

Not looking for the polished version — the honest one is more useful.

Sheyi

Reply 'stop' to opt out.
```

## Email 3 — Day 7

```
Hi {{first_name}},

One thing I keep hearing.

A recruitment agency I spoke to last week said their pipeline is basically feast or famine — strong months, then it dries up completely with no warning. Said they're still prospecting the same way they did five years ago because nothing better exists.

Is that pattern familiar at {{company_name}}, or does your pipeline feel more predictable?

Sheyi

Reply 'stop' to opt out.
```

## Email 4 — Day 10

```
Hi {{first_name}},

Last one from me.

I'm deciding this week whether to build something here or shelve it. If finding new clients isn't actually a live problem at {{company_name}}, that's genuinely useful — it'd point me somewhere else.

Either way, thanks for your time.

Sheyi

Reply 'stop' to opt out.
```

---

## Template Variables

- `{{first_name}}` — fallback: omit greeting, start body directly
- `{{company_name}}` — fallback: "your business"
- `{{industry_peer}}` — resolved from SIC code or industry keyword; fallback: "service business owner"
- `{{original_subject}}` — from sent_log.json first send subject

## Rules

- Any reply → stop sequence
- Unsubscribe → suppression list
- Email 2: +72h, Email 3: +168h, Email 4: +240h