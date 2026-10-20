// Lab 2: "The app that trusts everyone". DELIBERATELY VULNERABLE: a customer portal and an orders API for the
// learner to find and fix, in their own playground. Synthetic data only (@example.invalid). Node.js built-ins only,
// so there are no dependencies to install or audit.
//
// One file, two roles (app setting BW_ROLE): "portal" serves the public page, "api" serves orders as JSON.
// Each weakness is marked VULNERABLE (scenario). Fork this into your own repo, fix it, then redeploy:
//   az webapp deploy --resource-group <group> --name <app> --src-path app.zip --type zip
"use strict";

const http = require("node:http");
const { deriveToken, expectedToken } = require("./derive");

const ROLE = process.env.BW_ROLE === "api" ? "api" : "portal";
const PORT = Number(process.env.PORT) || 8080;
// Set by the kit's IaC from your seed. Keep them in your own IaC: the checks use them to recognise your app.
const LAB = process.env.BW_LAB || "app-trusts-everyone";
const SEED = process.env.BW_SEED || "";

// ---------- synthetic orders ----------
// Twelve made-up orders, spread across three made-up customers. Set BW_DEMO_OWNER_OID to your own Entra object ID
// to own orders 1 and 2, so you can test your authorisation fix while signed in as yourself.
const SYNTHETIC_OWNERS = [
  "00000000-0000-4000-8000-000000000001",
  "00000000-0000-4000-8000-000000000002",
  "00000000-0000-4000-8000-000000000003",
];

function orders() {
  const marker = SEED ? deriveToken(LAB, SEED, "orderMarker") : "unset";
  const demo = process.env.BW_DEMO_OWNER_OID;
  return Array.from({ length: 12 }, (_, i) => {
    const id = i + 1;
    const ownerId = demo && id <= 2 ? demo : SYNTHETIC_OWNERS[i % SYNTHETIC_OWNERS.length];
    return {
      id,
      ownerId,
      customerEmail: `customer${String((i % 3) + 1).padStart(2, "0")}@example.invalid`,
      items: [{ sku: `SKU-${1000 + id}`, quantity: (id % 3) + 1 }],
      totalGbp: Number((19.99 * ((id % 4) + 1)).toFixed(2)),
      exportMarker: marker, // seed-derived: lets the Verifier tell your app's data from anyone else's
    };
  });
}

// The signed-in caller, as App Service's built-in authentication reports it. App Service sets this header on
// requests it has authenticated. Without built-in auth in front of the app, anyone can send it, so it means nothing.
function callerId(req) {
  const id = req.headers["x-ms-client-principal-id"];
  return typeof id === "string" && id ? id : null;
}

// ---------- responses ----------
function send(res, status, body, type) {
  // VULNERABLE (scenario): no security headers at all. A hardened app sets at least Strict-Transport-Security,
  // X-Content-Type-Options and a Content-Security-Policy with frame-ancestors.
  res.writeHead(status, { "Content-Type": type, "Cache-Control": "no-store" });
  res.end(body);
}
const json = (res, status, value) => send(res, status, JSON.stringify(value, null, 2) + "\n", "application/json; charset=utf-8");
const notFound = (res) => json(res, 404, { error: "not found" });

const PAGE = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contoso Fintech customer portal</title></head>
<body>
<main>
<h1>Contoso Fintech customer portal</h1>
<p>Welcome. This is a training app for Bastionworks lab 2. Everything here is synthetic.</p>
<p>Orders are served by the orders API.</p>
</main>
</body>
</html>
`;

function portal(req, res, path) {
  if (path === "/") return send(res, 200, PAGE, "text/html; charset=utf-8");
  // VULNERABLE (scenario): a "temporary" debug page, still switched on in production.
  if (path === "/debug/config" && process.env.BW_DEBUG === "on") {
    return json(res, 200, {
      service: "customer-portal",
      environment: "production",
      build: "2026.10.02-1842",
      ordersApi: process.env.BW_ORDERS_API_URL || "unset",
      featureFlags: { newCheckout: true, debugEndpoints: true },
      deploymentToken: SEED ? expectedToken(LAB, SEED, "found-leak") : "unset", // the lab's token: record it
      note: "TODO remove before go-live",
    });
  }
  return notFound(res);
}

function api(req, res, path) {
  if (path === "/api/health") return json(res, 200, { status: "ok" });
  if (path === "/api/orders") {
    const me = callerId(req);
    return json(res, 200, orders().filter((o) => me !== null && o.ownerId === me));
  }
  const match = /^\/api\/orders\/(\d{1,6})$/.exec(path);
  if (match) {
    const order = orders().find((o) => o.id === Number(match[1]));
    if (!order) return notFound(res);
    // VULNERABLE (scenario): broken object-level authorisation (OWASP API1:2023). Any caller gets any order by
    // its sequential number. Nothing checks that the order belongs to the caller.
    return json(res, 200, order);
  }
  return notFound(res);
}

http
  .createServer((req, res) => {
    let path;
    try {
      path = new URL(req.url, "http://localhost").pathname;
    } catch {
      return json(res, 400, { error: "bad request" });
    }
    if (req.method !== "GET" && req.method !== "HEAD") return json(res, 405, { error: "method not allowed" });
    return ROLE === "api" ? api(req, res, path) : portal(req, res, path);
  })
  .listen(PORT, () => console.log(`${ROLE} listening on ${PORT}`));
