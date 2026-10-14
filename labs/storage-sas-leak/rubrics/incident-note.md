# Rubric: incident note for the CISO (storage-sas-leak)

Published so you know exactly how your note is reviewed. Each criterion is scored 0–2: 0 = missing, 1 = present but vague, 2 = specific and correct. Passing needs 8 of 12, with no 0 on criteria 1–3.

| # | Criterion | What a 2 looks like |
|---|---|---|
| 1 | **What was exposed** | Names the storage account and container, the permissions the SAS granted (from `sp=`) and its expiry (from `se=`). Says the data was synthetic in this exercise |
| 2 | **Exposure window** | When the token was issued and published (from the log timestamps) and when you revoked it, with times |
| 3 | **Containment** | Exactly how the token was made useless (which key rotated, or shared-key access disabled), and why that works for an ad-hoc SAS |
| 4 | **Root causes** | Both causes: a secret written to CI logs, **and** logs published to an anonymously readable container |
| 5 | **Evidence it's fixed** | How you verified: the token now returns 403, anonymous reads fail, and authorised reads still work |
| 6 | **Prevention** | Concrete, owned follow-ups: the IaC settings, log redaction or secret masking in CI, and a policy or alert so it can't recur |

Write for a CISO: lead with impact and status, keep it under one page, and avoid tool walkthroughs.
