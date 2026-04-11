# Auto-Reply Templates

These are the responses sent when a lead replies to the initial outreach. The classifier in `scripts/monitor_responses.py` decides which template to use based on the incoming message.

**Signing off:** Always end with "Sheyi" (no signature block — keeps it feeling like a normal conversation)

---

## Template 1 — Interested response

**Triggered when:** Lead asks questions, shares pain points, or expresses positive sentiment.

```
Hi {{first_name}},

Really appreciate the reply. That's exactly the kind of feedback I'm looking for.

A couple of follow-ups if you don't mind:

1. If a tool could solve {{specific_pain_they_mentioned}}, roughly how much time or money would it save your team per month?
2. What would you realistically pay for something like that? (Totally informal — just trying to gauge whether the economics work.)
3. Is there anything you've tried before that didn't work well enough?

Thanks for being so helpful — this directly shapes what we build.

Sheyi
```

**Variables:**
- `{{first_name}}` — from leads.json
- `{{specific_pain_they_mentioned}}` — extracted from their reply. If no specific pain mentioned, substitute the concept's generic pain (e.g. for Concept B: "cold outreach being expensive and low-converting")

---

## Template 2 — Pricing question

**Triggered when:** Lead asks about cost, "how much", pricing, or similar.

```
Hi {{first_name}},

Great question. I'm actually testing a few price points to see what makes sense:

- {{low_price}} — basic monitoring/features
- {{mid_price}} — full features + alerts
- {{high_price}} — everything + priority support

Which tier feels right for what you'd need? Or does a completely different model (per user, per project, usage-based) make more sense for your team?

No commitment — just figuring out the right structure.

Sheyi
```

**Price variables per concept:**

| Concept | Low | Mid | High |
|---------|-----|-----|------|
| A — ComplianceWatch | £49/month | £99/month | £199/month |
| B — LeadPulse | £29/month | £79/month | £149/month |
| C — MetricShield | £39/month | £99/month | £199/month |
| D — ProcessFlow | £59/month | £129/month | £249/month |

---

## Template 3 — Question / "Who are you"

**Triggered when:** Lead asks who you are, what the company does, or for more background before answering.

```
Hi {{first_name}},

Good question — I'm Sheyi, founder of T&O Ventures. We're a small product studio that builds software tools for businesses.

Right now I'm in research mode — talking to people like you to understand whether {{concept_one_liner}} is something companies would actually pay for before we build it.

Your perspective would be really valuable. {{restate_original_question}}

Cheers,
Sheyi
```

**Variables:**
- `{{concept_one_liner}}` — pulled from saas_concepts.md for the lead's assigned concept
- `{{restate_original_question}}` — pulled from the Email 1 body's key question for that concept

---

## Template 4 — Unsubscribe

**Triggered when:** Lead says stop, unsubscribe, remove me, not interested in future emails, or similar.

```
Hi {{first_name}},

Completely understood — I've removed you from any future emails. Apologies for the interruption.

All the best,
Sheyi
```

**Critical:** After sending this reply, add the email to `02-leads/suppression_list.json` IMMEDIATELY. Never send to them again, on any concept, for any reason.

---

## Template 5 — Not interested (soft no)

**Triggered when:** Lead says "not for us," "doesn't apply," "we have something already" (without asking to unsubscribe).

```
Hi {{first_name}},

No worries at all — appreciate you taking the time to respond. If things change in the future, feel free to get in touch.

All the best,
Sheyi
```

**Then:** Set lead status to `closed_not_interested`. Do NOT add to suppression list (they didn't ask) but do NOT send further emails for this concept.

---

## Template 6 — Auto-reply / Out of office

**Triggered when:** Incoming email is clearly an OOO bounce ("I am out of the office until...").

**Action:** Do not reply. Parse the return date if possible. Schedule the next email in the sequence for return_date + 1 day. Log in responses.json with classification `auto_reply`.

---

## Classification priority

If a reply matches multiple categories, use this priority order:

1. **Unsubscribe** (absolute priority — if "stop", "unsubscribe", "remove" present, always classify as unsubscribe)
2. **Auto-reply** (out of office, delayed delivery, system messages)
3. **Pricing question** (explicit "how much", "cost", "price")
4. **Question** (who are you, tell me more, what's this)
5. **Interested** (positive tone, shares pain, asks clarifying questions)
6. **Not interested** (default for anything negative but not explicit unsubscribe)
