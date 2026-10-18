# Rubric: runbook entry for the password-spray rule (password-spray)

Published so you know exactly how your entry is reviewed. Each criterion is scored 0–2: 0 = missing, 1 = present but vague, 2 = specific and correct. **Passing needs 8 of 12, with no 0 on criteria 1–3.**

| # | Criterion | What a 2 looks like |
|---|---|---|
| 1 | **What it detects** | Says, in plain words, the behaviour it catches: one address failing against many accounts, then a success. Names MITRE ATT&CK T1110.003 (password spraying) |
| 2 | **How it decides** | Explains the logic and the thresholds you chose (for example, the number of distinct failed accounts per address and the time window) and why those numbers |
| 3 | **Known false positives and tuning** | Names realistic benign causes (users mistyping, a shared office or carrier address, a misconfigured service account) and how to tune for each without hiding a real spray |
| 4 | **First response** | Concrete steps for the on-call analyst: confirm the sign-in with the user, revoke their sessions, reset the password, and check what the account did after the success |
| 5 | **Containment and follow-up** | Blocking or investigating the spraying addresses, checking the other targeted accounts, and longer-term fixes (for example, enforcing MFA and banned-password lists) |
| 6 | **Limits** | What the rule would miss: a slow spray spread over days, many rotating addresses, or a spray against a single account, and what would catch those |

Write for an analyst who is woken at 3 a.m.: short sections, clear steps, no padding.
