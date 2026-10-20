# Ticket SEC-0207: Pen-test findings on the customer portal and orders API

| | |
|---|---|
| **Requester** | Ines Mwangi, Head of Application Security, Contoso Fintech |
| **Assignee** | You (Cloud Security Engineer) |
| **Priority** | P2, fixed and evidenced before Thursday's change board |
| **Scope** | The two apps deployed by this lab, in **your** resource group only, and your own Entra tenant |

## Context
The pen testers sent a summary ahead of their full report. On the customer portal and its orders API they found:
- the portal answers over **plain HTTP**;
- both apps will share their responses with **any website that asks** (CORS);
- the apps still accept **FTP and username-and-password publishing**;
- a "temporary" **debug page** is live in production;
- the portal sends **no security headers**;
- the orders API needs **no sign-in**;
- anyone can read **any customer's order** by changing the number in the URL.

Everything in this lab is synthetic (`@example.invalid` customers), but treat it as if it weren't.

`bw deploy` printed your two apps:
- portal: `http://<your portal>.azurewebsites.net/`
- orders API: `http://<your API>.azurewebsites.net/api/orders/1`

The app's code is in the kit's `app/` folder. It's Node.js with no dependencies.

## What "done" looks like
1. **Look before you fix.** Open the debug page, and note what it gives away, including the `deploymentToken` (you'll submit it). Then try the API: read an order, then another customer's.
2. **Harden the platform settings for both apps:**
   - HTTPS only;
   - no FTP;
   - no basic-auth publishing;
   - TLS 1.2 or higher;
   - CORS limited to the origins that really need it (the portal needs none).
3. **Turn the debug page off.**
4. **Require sign-in on the API** with App Service's built-in authentication and Microsoft Entra ID. Use the app registration in **your own** tenant, and answer unauthenticated calls with **401**.
5. **Fix the code in your own fork,** then redeploy it:
   - the portal sends `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, and a `Content-Security-Policy` with `frame-ancestors`;
   - the API only returns an order to the customer who owns it.

   Set `BW_DEMO_OWNER_OID` to your own Entra object ID, so you own orders 1 and 2 and can test this.
6. **Make it stay fixed:** declare both apps in **Bicep** in your own public repo, with every setting above.
7. **Write the security review** for the change board.

To redeploy your fixed code (it works with basic auth off, because the CLI falls back to Entra):
```
cd app && zip -r ../app.zip . && cd ..
az webapp deploy --resource-group <your lab group> --name <app> --src-path app.zip --type zip
```

## Rules of engagement
- Work only in your own lab resource group and your own tenant.
- Don't delete and recreate the apps to "fix" them. The checks look for your seed-named apps, still answering.
- Keep `BW_LAB` and `BW_SEED` in your apps' settings: the checks use them to recognise your apps.
- Built-in authentication proves **who** is calling. It doesn't decide **what** they may read: that's your code.

## Checkpoints
| Checkpoint | How it's checked | Trust |
|---|---|---|
| You found what the debug page leaks | Submit the `deploymentToken` from the debug page. It records that you looked, on your word | Self-reported |
| The portal is locked down, checked from outside | Submit your portal's URL. The platform checks four things: `http://` redirects permanently to `https://`; a request from `https://evil.example` isn't granted CORS; `/debug/config` is a 404; and the three headers are present. Your home page must still answer 200 | Verified |
| The orders API refuses anonymous callers | Submit your API's URL. An anonymous `GET /api/orders/1` must get 401 with no order data, a hostile origin isn't granted CORS, and the Entra sign-in endpoint is live | Verified |
| Your IaC keeps both apps fixed | Submit your **public** GitHub repo at a full 40-character commit SHA. The platform compiles your Bicep and checks both apps that use your seed-derived names | Verified |
| Explain what each fix does, and what it doesn't | A short knowledge check: your own set of questions. You see your score, not which answers were wrong | Reviewed |
| Write the security review for the change board | Commit it as **`security-review.md` at the root** of the same repo, and submit the repo at a commit. It's reviewed against the published rubric (`rubrics/security-review.md`) | Reviewed |

The object-level fix (only your own orders) is **Reviewed**, not Verified. Testing it live would mean the platform signing in as users in your tenant, and Bastionworks never does that.

## Cost
About **$0**. Both apps run on one Free (F1) plan. Run `bw cleanup app-trusts-everyone` when you're done. Your Entra app registration isn't removed by cleanup: delete it in **Entra ID > App registrations** if you don't need it.
