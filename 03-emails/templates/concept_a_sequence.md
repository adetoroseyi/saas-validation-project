# Concept A — ComplianceWatch — Email Sequence

**Concept:** ComplianceWatch
**One-liner:** Automated compliance monitoring that alerts you before violations happen.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 3 touches over 7 days
**Footer (every email):** "Reply 'stop' to opt out."

---

## Email 1 — Day 0 — The Question

**Subject line variants (rotate, A/B test):**
1. compliance gap
2. a risk question
3. audit prep at {{company_name}}

**Body:**

```
Hi {{first_name}},

Most people I speak to who handle compliance at businesses like yours say the same thing — they only find out there's a gap when it's already a problem. By then it's a scramble.

I'm looking into whether there's a way to flag those gaps earlier, before they turn into violations or missed deadlines.

Quick honest question: how does {{company_name}} currently stay on top of compliance requirements — is it mostly manual, outsourced, or do you have something in place?

I'm in early research and genuinely looking for a 'no, this isn't a real problem' as much as a 'yes.'

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

Just a brief follow-up.

A finance director I spoke to last week said their team tracks everything in a spreadsheet and a folder of PDFs — and they've still missed things. Said it's not the major regulatory changes that catch them out, it's the tiny, stupid updates that slip through and nobody noticed until it was too late.

Curious if that pattern sounds familiar at {{company_name}}, or if you've found a better way to manage it.

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

I'm trying to decide whether to kill this project or commit to it. Feedback from people actually dealing with compliance day-to-day has been worth more than any industry report.

If staying on top of compliance isn't a real headache at {{company_name}}, no need to reply — that's useful data too.

If it is, one sentence on how you currently handle it would go a long way.

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

- If `first_name` is missing, use "there" (never "undefined" or blank)
- If `company_name` is missing, the lead is NOT eligible for Concept A — skip
- Always send Email 1 on a weekday morning (8:00-11:00 AM recipient local time)
- Email 2 is sent at the same time of day as Email 1 + 72 hours
- Email 3 is sent at the same time of day as Email 1 + 168 hours (7 days)
- Any reply to any email → stop the sequence immediately
- Unsubscribe → add to suppression list, never send again
