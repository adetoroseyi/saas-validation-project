# Concept B — LeadPulse — Email Sequence

**Concept:** LeadPulse
**One-liner:** See exactly which companies are looking for your services right now.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 3 touches over 7 days
**Footer (every email):** "Reply 'stop' to opt out."

---

## Email 1 — Day 0 — The Question

**Subject line variants (rotate, A/B test):**
1. question re: referral process
2. how does {{company_name}} find new work
3. lead tracking at {{company_name}}

**Body:**

```
Hi {{first_name}},

Most {{industry_peer}}s I've spoken to say the same thing — referrals keep the lights on, but they can't tell you when the next one's coming.

I'm looking into whether there's a better way to spot businesses that are actively looking for services like yours — before they've posted a brief or gone to a competitor.

One honest question: where does most of {{company_name}}'s new work actually come from — is it mostly word of mouth, or are you running active outbound or ads?

I'm in early research and genuinely looking for a 'no, this isn't a real problem' as much as a 'yes.'

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

Quick follow-up.

A recruiter at a mid-size firm I grabbed 10 minutes with last week said their pipeline is basically feast or famine — a few strong months, then it dries up completely with no warning. Said they're still prospecting on LinkedIn the same way they did five years ago because nothing better exists.

Curious whether that pattern sounds familiar for {{company_name}}, or whether your pipeline feels more predictable.

Either answer is useful — cheers,
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

I'm trying to decide whether to kill this project or commit to it. Honest input from people actually running service businesses has been more useful than any market report.

If finding new clients isn't a live problem at {{company_name}}, no need to reply — that's useful data too.

If it is, one sentence on where your clients currently come from would go a long way.

Either way — thanks for the time.

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
| `{{industry_peer}}` | Set per lead segment — see values below |

**`{{industry_peer}}` values by segment:**
- Marketing / creative agencies → `agency owner`
- IT / tech consultants → `IT consultant`
- Recruiters / staffing firms → `recruiter`
- Management consultants → `consultant`
- Default fallback → `service business owner`

**Segment observation variants (Email 1, line 1):**
The default observation "referrals keep the lights on, but they can't tell you when the next one's coming" works well for agencies and recruiters. For IT and management consultants, swap for a sharper variant:

- IT consultants: *"Most IT consultants I've spoken to say the same thing — the work comes from who you know, but there's no reliable way to know who's actually looking right now."*
- Management consultants: *"Most consultants I've spoken to say the same thing — mandates come through relationships, but there's no way to see who's in the market for one before they've already chosen someone."*

## Rules

- If `first_name` is missing, use "there"
- If `company_name` is missing, skip lead
- Set `industry_peer` based on the lead's SIC code or source tag before sending — never use the raw variable name
- Send Email 1 on a weekday 8:00-11:00 AM recipient local time
- Email 2: +72 hours
- Email 3: +168 hours
- Any reply → stop sequence
- Unsubscribe → add to suppression list
