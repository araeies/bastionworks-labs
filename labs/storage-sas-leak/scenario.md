# Ticket SEC-0142: Possible credential exposure in CI logs

| | |
|---|---|
| **Requester** | Tunde Bakare, Head of Data Engineering, Contoso Fintech |
| **Assignee** | You (Cloud Security Engineer) |
| **Priority** | P1, contain within 1 hour, fully closed by end of day |
| **Scope** | The storage account deployed by this lab, in **your** resource group only |

## Context
A contractor flagged that build logs from the `nightly-customer-export` pipeline are being published to a storage container, and that "anyone can open them without signing in". One log from run #1842 appears to contain a URL with a long string on the end.

The export container holds customer data. Everything in this lab is synthetic, but treat it as if it weren't.

Your starting point is the public URL `bw deploy` printed:
`https://<your storage account>.blob.core.windows.net/build-artifacts/pipeline-logs/build-1842.log`

## What "done" looks like
1. **Contain:** the URL in the log no longer grants access to anything.
2. **Close the exposure:** nothing in the account is readable without authentication.
3. **Prove the account is still healthy:** you can still read data with a credential you issue, scoped to the minimum.
4. **Prevent recurrence:** your own IaC for this account makes both mistakes impossible to deploy again.
5. **Report:** a short incident note for the CISO.

## Rules of engagement
- Work only in your own lab resource group.
- Do **not** delete and recreate the storage account to "fix" it. In production you'd lose the data and the evidence, and the checkpoints detect it.
- Keep a timeline as you go: what you found, when, and what you changed. You'll need it for the report.

## Checkpoints
| Checkpoint | How it's verified | Trust |
|---|---|---|
| The leaked token no longer works | Submit the leaked URL; the platform makes one request and expects a refusal. The URL is redacted before anything is stored | Verified |
| The original account still serves data, securely | Submit a read-only SAS **you** issue for `customer-exports/status/healthcheck.txt`, valid 60 minutes or less | Verified |
| The build log is no longer publicly readable | Submit the build-log URL; the platform requests it without credentials | Verified |
| Your IaC prevents it happening again | Submit your **public** GitHub repo at a full 40-character commit SHA. The platform compiles your **Bicep** (Terraform isn't supported yet) and checks the storage account that uses your account name | Verified |
| Incident note for the CISO | Commit the note as **`incident-note.md` at the root** of the same repo and submit the repo at a commit. It's reviewed against the published rubric (`rubrics/incident-note.md`) | Reviewed |
