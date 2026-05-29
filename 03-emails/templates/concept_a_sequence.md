# Concept A — ComplianceWatch — Email Sequence

**Concept:** ComplianceWatch
**One-liner:** Automated compliance tracking so nothing slips through the gaps.
**Sender:** Sheyi A <sheyi@trysignalbench.com>
**Sequence:** 4 touches over 10 days
**Target:** Property management leads only — reassign other industries to Concept D.

---

## Subject Line Variants

**Email 1 (rotate, A/B test):**
1. `HMO licence renewal`
2. `landlord compliance at {{company_name}}`
3. `compliance gap`

**Emails 2–4:** `Re: {{original_subject}}`

---

## Email 1 — Day 0

```
Hi {{first_name}},

A property manager I spoke to recently tracks EPC certificates, gas safety renewals, and section 21 timelines in a shared spreadsheet. Said they've never missed a deadline — but when I asked what their backup was if the person who runs it left, they went quiet.

I'm looking into whether there's a better way to track this kind of thing — one that doesn't depend on one person knowing where everything lives.

Is that a real risk at {{company_name}}?

I'm in early research — genuinely as useful to hear "we've solved this" as "yes, it's a problem."

Sheyi

Reply 'stop' to opt out.
```

## Email 2 — Day 3

```
Hi {{first_name}},

Different angle on this.

Most property managers I've spoken to have already tried to fix the compliance tracking problem — usually a spreadsheet that grew arms, a calendar reminder system someone set up years ago, or a folder structure that only one person understands. The fix kind of works, until it doesn't.

Has {{company_name}} gone down any of those roads? Curious what you tried and what fell short.

Sheyi

Reply 'stop' to opt out.
```

## Email 3 — Day 7

```
Hi {{first_name}},

One thing I keep hearing.

A lettings manager I spoke to last week said their team tracks HMO licence renewals in a shared Google Sheet — one tab per property, colour-coded by who owns the task. Said it works fine until someone leaves and nobody knows which colours mean what.

Is there a process like that at {{company_name}} — something that technically works but depends on one person keeping it alive?

Sheyi

Reply 'stop' to opt out.
```

## Email 4 — Day 10

```
Hi {{first_name}},

Last one from me.

I'm deciding this week whether to build something here or shelve it. If compliance tracking isn't actually a pain at {{company_name}}, that's genuinely useful — it'd point me somewhere else.

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

- Only send to leads where industry contains "property management" or "real estate" or "lettings"
- Reassign all other Concept A leads to Concept D before sending
- Any reply → stop sequence
- Unsubscribe → suppression list
- Email 2: +72h, Email 3: +168h, Email 4: +240h