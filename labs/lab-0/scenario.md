# Ticket SEC-0001: Stand up a safe security sandbox

| | |
|---|---|
| **Requester** | Adaeze Okafor, Head of Cloud Platform, Contoso Fintech |
| **Assignee** | You (Cloud Security Engineer, week 1) |
| **Priority** | P2, due before you touch any other ticket |
| **Scope** | One **dedicated** Azure subscription that you own. Never a work, production or shared subscription |

## Context
Contoso Fintech's security team is starting a hands-on programme. Several of the exercises deploy deliberately vulnerable or "compromised" infrastructure. Last year a contractor ran a penetration-test script in a shared subscription and took down a payments sandbox for a day; the bill for a forgotten GPU VM was worse.

Before you get any attack-and-defend tickets, the platform team needs proof that your sandbox **cannot** hurt anything else and **cannot** run up a surprise bill.

## What "done" looks like
1. The subscription is dedicated to this work. MFA is on for your account.
2. A monthly budget exists, with alerts that fire early (well before you'd notice a bill).
3. Guardrail policies stop resources landing in unexpected regions, block large VM sizes, and deny resource types that are expensive by default.
4. The subscription carries the tag `bastionworks:playground=true`. Every later kit refuses to deploy anywhere without it.
5. Your own Git repo holds the guardrails **as code**, so you could rebuild them from scratch.

## Rules of engagement
- Work only in the subscription you created for this programme.
- Do not disable or weaken these guardrails to get a later lab working. Raise it as a question instead.

## How to start
In Azure Cloud Shell, with the subscription selected (`az account show`):

```bash
bw deploy lab-0 --seed <your seed> --version <version> --sha256 <hash>
bw doctor
```

Every Azure command `bw` runs is printed first. Read them: you will write your own version of the same guardrails for the checkpoint.

## Checkpoints
- **Guardrails as code** (Verified, artefact scan): push Bicep (or Terraform) that declares the allowed-locations and denied-resource-types policy assignments and a budget named with your playground ID, then submit the repo at a commit.
- **Why it matters** (Reviewed, knowledge check): a few questions on what these guardrails do *not* protect against.
