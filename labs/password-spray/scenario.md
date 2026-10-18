# The 3 a.m. sign-in

**Ticket SEC-0217 · Detection engineering · Intermediate · about 60 minutes · costs nothing**

> **From:** Identity team lead, Contoso (lab)
> **To:** Detection engineering
>
> We were paged at 03:12 last night. Somebody tried a password against a long list of our accounts in a short burst, and at least one of those accounts then signed in successfully. We don't have a rule for this, and the last attempt at one alerted every time someone mistyped their password. Can you write us a **Microsoft Sentinel analytics rule** that catches "password spray, then success" without burying the on-call analyst?

## What you'll do
1. **Explore the practice data.** `data/practice.kql` is a day of synthetic sign-in logs shaped like Entra ID `SigninLogs`, with one overnight spray in it.
   - Open any Log Analytics workspace (a free one is fine) and go to **Logs**.
   - Paste the whole file into the query window and run it. It shows 10 rows.
   - Then replace the last two lines with your own query.
   - There's nothing to upload and no ingestion cost: the data travels inside your query.
   - `data/signin-sample.csv` has the same events, if you'd rather use another tool.
2. **Write the rule.** Find the accounts that were signed in to successfully as part of the spray. The data also contains ordinary noise that looks a bit like an attack, and your rule must not flag it.
3. **Commit it** to a repository in your GitHub account as **`detections/password-spray.kql`**. Commit just the rule, starting from `SigninLogs`, without the practice data.
4. **Write the runbook entry** for the on-call analyst, in **`detections/password-spray.md`**. See `rubrics/runbook-entry.md` for what a good one covers.
5. **Submit both** on the lab page, as your repo at a commit.

## What your rule must return
One row per suspected compromised sign-in, with at least a **`UserPrincipalName`** column. `IPAddress` and `TimeGenerated` help the analyst too. Use `summarize`, `join` or anything else you like: the check looks at which accounts you flag.

## How it's checked
- **Your rule catches the attack (Verified).** The Verifier runs your rule against **different, unseen** sign-in data, with its own attack, its own noise and your own variant. It reports how many attacked accounts you caught and how many false alarms you raised.
  - **To pass:** catch every attacked account, with at most 2 false alarms.
  - You never see the hidden data, and the result never says which accounts.
  - Hard-coding the practice data's addresses or names won't carry over.
  - 10 checks a day.
- **Your runbook entry (Reviewed).** It's scored against the published rubric.

## Rules of the road
- Query `SigninLogs` only. Cross-workspace and external functions (`workspace()`, `app()`, `externaldata`, `evaluate` and so on) and management commands are refused.
- Keep the rule under 8 KiB.
- Everything in this lab is synthetic: the `contoso-lab.example` accounts and the documentation-range IP addresses.

## Cheapest real Microsoft Sentinel option
You don't need Sentinel for this lab. If you want to try your rule as a real scheduled analytics rule:
- Microsoft Sentinel offers a **free trial** on a new Log Analytics workspace (check the current terms on Microsoft's Sentinel pricing page before you start).
- To keep cost at zero, add the rule, then delete the workspace when you're done.
