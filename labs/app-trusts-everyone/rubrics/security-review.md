# Rubric: security review for the change board (app-trusts-everyone)

Published so you know exactly how your review is scored. Each criterion is scored 0–2: 0 = missing, 1 = present but vague, 2 = specific and correct. Passing needs 10 of 14, with no 0 on criteria 1, 3 or 4.

| # | Criterion | What a 2 looks like |
|---|---|---|
| 1 | **Findings, with severity** | Every weakness from the ticket, each with a severity and one line on the impact: plain HTTP, wildcard CORS, basic-auth publishing and FTP, the debug page, missing security headers, the unauthenticated API, and any customer's order readable by number |
| 2 | **The fix for each** | What you changed for each finding, and where: platform setting, IaC, or app code |
| 3 | **Object-level authorisation, in code** | Shows (a snippet or a link to the commit) how the API now checks that an order belongs to the caller, and what it returns when it doesn't (404 or 403, and why you chose it) |
| 4 | **Authentication vs authorisation** | Explains that built-in auth only proves *who* is calling, and that the code fix decides *what* they may read. Notes the principal header can only be trusted with built-in auth in front |
| 5 | **Evidence it's fixed** | How you checked each fix from outside: the redirect, the hostile-origin request, the 404 on the debug page, the headers, the 401 for anonymous calls, and a signed-in caller who can read their own order but not someone else's |
| 6 | **Residual risk** | What's still not covered, and what you'd do next: for example no WAF or rate limiting on the Free plan, shared infrastructure, a token for any user in your tenant unless assignment is required, and secrets the debug page may have exposed |
| 7 | **Prevention** | Owned follow-ups that stop a repeat: the IaC settings, Azure Policy for HTTPS-only, FTP and basic auth, a pre-release check for debug routes, and security headers set in one shared place |

Write for a change board: lead with risk and status, keep it to about a page, and avoid tool walkthroughs.
