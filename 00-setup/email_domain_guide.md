# Email Domain + Warmup Setup Guide

**For:** Sheyi Olu / T&O Ventures Ltd
**Recommended sending domain:** `trysignalbench.com`
**Recommended sending email:** `sheyi@trysignalbench.com`
**Recommended display name:** `Sheyi Olu`
**Personal Gmail (do NOT use for outreach):** `olubusinessempire@gmail.com`

> This is a checklist you execute yourself. Claude cannot buy domains, create accounts, or authorise access on your behalf — those are prohibited actions for safety reasons. Work through each step in order and tick them off. Total active work: ~90 minutes across 2 days. Warmup waiting time: ~10-14 days before first cold send.

---

## Why a separate domain matters (read this first)

You asked whether you could buy a domain and keep sending from `olubusinessempire@gmail.com` with a different display name. You can change the display name in 30 seconds, but that **does not** protect you:

- Recipients still see `olubusinessempire@gmail.com` as the real From address
- Any spam reports damage your personal Gmail reputation — your real personal/business email starts going to spam
- Google's consumer Gmail Terms of Service prohibit unsolicited bulk sending — your account can be suspended
- If the account is suspended you lose access to everything tied to it

The correct setup is a **separate Google Workspace account on a new domain**. Replies can still be forwarded to your personal Gmail so you can manage them in one inbox. Your personal account stays untouched.

---

## Step 1 — Buy the domain (~10 min, ~£8-25)

1. Go to **Namecheap** (https://namecheap.com) or **Porkbun** (https://porkbun.com). Either is fine. Porkbun is usually cheaper; Namecheap has a slicker UI.
2. ✅ **Domain already purchased:** `trysignalbench.com` — verified and Gmail activated.
3. Steps 1-2 are complete. Continue from Step 3 (DNS authentication).
5. At checkout:
   - **Turn ON WhoisGuard / Domain Privacy** (free with Namecheap, essential — hides your personal details from public WHOIS lookups)
   - Skip all upsells (SSL, website builder, premium DNS — you don't need any of them)
   - Auto-renew ON is fine
6. ✅ You now own the domain. Note it down — **from now on wherever you see `trysignalbench.com` in this project, replace it with the actual domain you bought if different.**

---

## Step 2 — Set up Google Workspace (~20 min, ~£5/month)

1. Go to https://workspace.google.com
2. Click "Start free trial" (14-day free trial, then ~£5/month for Business Starter — the cheapest plan is enough)
3. When asked for business name: **T&O Ventures Ltd**
4. Number of employees: **Just you**
5. Region: **United Kingdom**
6. Contact info: use your existing details
7. When asked "Does your business have a domain?" → **Yes**
8. Enter the domain you just bought (e.g. `trysignalbench.com`)
9. Create your admin user:
   - Username: **sheyi**
   - This creates `sheyi@trysignalbench.com` as your Workspace admin account
   - Choose a strong password (not the same as your personal Gmail)
10. Complete checkout. You can skip phone/billing verification bits that are optional.
11. You'll land in the **Google Admin Console** at admin.google.com.
12. ✅ Workspace is live, but the domain still needs DNS verification (Step 3).

---

## Step 3 — DNS authentication (SPF, DKIM, DMARC) — ~30 min

This is the most important step. Without these records, your emails land in spam no matter what you write.

### 3a. Verify the domain (Google will walk you through this)

1. In Google Admin Console, you'll see a "Verify your domain" prompt.
2. Google will give you a **TXT record** (starts with `google-site-verification=...`)
3. Open a new tab → log into Namecheap → Domain List → click **Manage** next to your domain → **Advanced DNS** tab
4. Click **Add New Record** → Type: **TXT Record** → Host: `@` → Value: paste the google-site-verification string → TTL: **Automatic**
5. Save. Go back to Google Admin and click **Verify**. (May take 5-60 minutes to propagate.)

### 3b. SPF record — tells the world Google is allowed to send on your behalf

In Namecheap Advanced DNS → Add New Record:
- **Type:** TXT Record
- **Host:** `@`
- **Value:** `v=spf1 include:_spf.google.com ~all`
- **TTL:** Automatic
- Save.

> If there's already a TXT record on `@` from the Google verification above, that's fine — SPF and verification TXT records can coexist.

### 3c. DKIM record — cryptographically signs your emails so they can't be spoofed

1. In Google Admin Console, go to **Apps → Google Workspace → Gmail → Authenticate email**
2. Select your domain from the dropdown
3. Click **Generate new record** (leave defaults: 2048-bit, prefix `google`)
4. Google shows you a TXT record. It will look like:
   - **DNS Host name:** `google._domainkey`
   - **TXT record value:** `v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3...` (very long string)
5. Back in Namecheap Advanced DNS → Add New Record:
   - **Type:** TXT Record
   - **Host:** `google._domainkey`
   - **Value:** paste the full DKIM string (must be the whole thing, no line breaks)
   - **TTL:** Automatic
   - Save.
6. Wait 10-30 minutes for DNS to propagate.
7. Back in Google Admin → **Authenticate email** → click **Start authentication**. It should change from "Not authenticating email" to "Authenticating email."

### 3d. DMARC record — tells receivers what to do with emails that fail SPF/DKIM

In Namecheap Advanced DNS → Add New Record:
- **Type:** TXT Record
- **Host:** `_dmarc`
- **Value:** `v=DMARC1; p=none; rua=mailto:sheyi@trysignalbench.com; pct=100; adkim=r; aspf=r`
- **TTL:** Automatic
- Save.

> We start with `p=none` (monitoring only, don't reject failing mail). After ~6 weeks of good deliverability you can tighten to `p=quarantine`.

### 3e. MX records — verify they're correct

Google Workspace automatically sets up MX records during onboarding, but double-check in Namecheap that these five exist on host `@`:

| Priority | Value |
|----------|-------|
| 1 | `smtp.google.com` |

(Modern Workspace uses a single MX record. If you see legacy `aspmx.l.google.com` / `alt1.aspmx...` etc., that's also fine and works.)

### 3f. Verify the setup

Once all DNS records are saved and ~30 minutes have passed:

1. Go to **https://mxtoolbox.com/SuperTool.aspx**
2. Run these checks on your domain:
   - **SPF Record Lookup** → should return your SPF with no errors
   - **DKIM Lookup** → selector `google` → should return the DKIM key
   - **DMARC Lookup** → should return your DMARC policy
   - **MX Lookup** → should return Google's servers
3. Also run **https://www.mail-tester.com**:
   - Copy the random email address it shows you
   - Send a test email from `sheyi@trysignalbench.com` to that address (any subject/body)
   - Check your score — aim for **9/10 or 10/10**
   - If below 8/10, mail-tester will tell you which record is missing or wrong — fix it before proceeding

✅ Once you hit 9/10 on mail-tester, your domain is **technically** ready to send. But reputation-wise it's still brand new and cold — that's what Step 4 fixes.

---

## Step 4 — Warm up the domain (14 days, ~£15-30)

Sending 80 cold emails a day from a brand new domain is the fastest way to get flagged as spam. Warmup builds up a reputation of sending real, two-way, human-looking email so receivers' filters learn to trust you.

### Recommended: Warmbox.ai (~£29/month, cancel after 1 month)

1. Go to https://warmbox.ai
2. Sign up for the "Starter" plan (~£29/month)
3. Click **Add Inbox** → choose **Google Workspace**
4. Complete the OAuth flow using `sheyi@trysignalbench.com`
5. Grant the permissions Warmbox needs (send and read mail)
6. Configure warmup settings:
   - **Ramp-up speed:** Medium (default)
   - **Daily limit day 1:** 4 emails
   - **Daily limit cap:** 40 emails
   - **Weekly increase:** +5 per day
   - **Reply rate:** 50% (recipients reply to ~half of the emails, simulating real conversation)
7. Start warmup. Warmbox will now automatically send small volumes of email from your inbox to its network of real inboxes, which will reply and mark as important. Do nothing — let it run.
8. **Keep warmup running for 10-14 days minimum** before any cold outreach.
9. Check the Warmbox dashboard daily — it shows deliverability scores across Gmail, Outlook, Yahoo. You want all showing "Inboxing" (green).

### Alternative: Lemwarm (~£22/month)
- Integrated with Lemlist. If you're planning to use Lemlist for sending later, pick this.
- Signup: https://lemwarm.com

### Alternative: Mailwarm (~£69/month)
- More established but pricier. Use only if Warmbox is down.

### What you should NOT do
- Don't send any cold outreach during warmup. Warmup + cold sending at the same time confuses the algorithm.
- Don't email your own other addresses to "test" — that doesn't build reputation.
- Don't skip warmup because "I only want to send 20 emails a day." Even 20 from a brand new domain triggers filters.

---

## Step 5 — Set up forwarding so replies come to your main Gmail (~5 min)

So you don't have to check two inboxes:

1. Log in to `sheyi@trysignalbench.com` webmail at https://mail.google.com
2. Click **Settings (gear icon) → See all settings → Forwarding and POP/IMAP**
3. Click **Add a forwarding address**
4. Enter `olubusinessempire@gmail.com`
5. Click Next → Proceed → OK
6. A confirmation code goes to your personal Gmail. Click the confirmation link.
7. Back in sheyi@trysignalbench.com settings → select **"Forward a copy of incoming mail to olubusinessempire@gmail.com"** → **"keep Gmail's copy in the Inbox"** (the second option — important so Claude can still read it via Gmail MCP)
8. Save.
9. ✅ Any reply to `sheyi@trysignalbench.com` now appears in BOTH your personal Gmail and the trysignalbench inbox. The trysignalbench copy is the one the automation reads.

**Optional:** Set up "Send mail as" in your personal Gmail so you can reply from `sheyi@trysignalbench.com` without leaving your normal Gmail interface. Settings → Accounts and Import → Send mail as → Add another email. Not required, but convenient.

---

## Step 6 — Connect Gmail MCP to the new account (~2 min)

Once warmup has been running for at least 10 days:

1. In Claude Desktop / Claude Code, go to Settings → Connectors → Gmail
2. Click **Disconnect** (this removes `olubusinessempire@gmail.com`)
3. Click **Connect** → sign in with `sheyi@trysignalbench.com`
4. Grant the same permissions as before
5. ✅ Claude now reads and sends from the signalbench inbox. Your personal Gmail is no longer exposed to this project.

**Important:** After reconnecting, tell Claude: "Gmail MCP is now connected to sheyi@trysignalbench.com. Please verify by calling gmail_get_profile and confirming the email address." This avoids any ambiguity.

---

## Step 7 — Final pre-flight check (before first real send)

Run all of these. Do not skip.

- [ ] Domain bought and WhoisGuard enabled
- [ ] Google Workspace account created (`sheyi@trysignalbench.com`)
- [ ] SPF record in place, passes MXToolbox
- [ ] DKIM record in place, Google Admin shows "Authenticating email"
- [ ] DMARC record in place, passes MXToolbox
- [ ] mail-tester.com score of 9/10 or 10/10
- [ ] Warmup ran for 10+ consecutive days with no drop in inbox rate
- [ ] Warmbox dashboard shows "Inboxing" (green) across Gmail + Outlook
- [ ] Forwarding from signalbench to personal Gmail is live
- [ ] Gmail MCP reconnected to `sheyi@trysignalbench.com`
- [ ] Test email sent from Claude via Gmail MCP to a friend → lands in **Inbox**, not Promotions or Spam
- [ ] Apify token available and working (already verified via Apify MCP in Claude)
- [ ] Reviewed `03-emails/templates/` and happy with tone
- [ ] Reviewed `01-concepts/saas_concepts.md` and happy with concept targeting

Once all boxes are ticked, come back to Claude and say: **"Pre-flight is complete. Start Day 1 of live outreach."** Claude will do the first controlled-volume send (25 emails) and monitor from there.

---

## Cost summary

| Item | Cost | Frequency |
|------|------|-----------|
| Domain (trysignalbench.com) | ~£25 | Per year |
| Google Workspace Business Starter | ~£5 | Per month |
| Warmbox.ai (during warmup) | ~£29 | One-off month |
| Apify (leads, usage-based) | ~£25-40 | Per month |
| **Total month 1** | **~£84** | |
| **Ongoing monthly (month 2+)** | **~£30-45** | |

---

## Troubleshooting

**"mail-tester score is 6/10 and it's flagging SPF"**
→ Your SPF record has a typo or there's a second conflicting SPF record. Namecheap DNS → find all TXT records on `@` → there should be exactly ONE starting with `v=spf1`. Delete duplicates.

**"Google Admin says 'DKIM not authenticating'"**
→ Give it longer — DNS propagation can take up to 48 hours. Use `dig TXT google._domainkey.trysignalbench.com` or the DKIM Lookup tool on mxtoolbox.com to confirm the record is visible publicly. If it's visible and still not authenticating after 2 hours, the DKIM value was truncated when pasted into Namecheap — generate a new key and paste again carefully.

**"Warmbox is showing emails landing in Spam"**
→ Normal for the first 2-3 days. If still spam after day 5, your DNS setup has an issue — re-run mail-tester and fix whatever's flagged before continuing warmup.

**"I bought a different domain name"**
→ In this project directory run a search-and-replace of `trysignalbench.com` → your domain across all files. Ask Claude: "Update the project to use `[your-domain]` instead of trysignalbench.com."

---

## What Claude will NOT do for you

For safety reasons, these steps must be done by you personally:

- Purchasing domains (financial transaction)
- Creating the Google Workspace account (account creation)
- Entering credit card details (sensitive financial data)
- Completing OAuth flows for Warmbox, Workspace, Gmail MCP (authorisation)
- Accepting terms of service (requires explicit user consent)
- Entering passwords (credentials)

Everything else in this project — content, data, scripts, analysis, outreach execution — runs through Claude.
