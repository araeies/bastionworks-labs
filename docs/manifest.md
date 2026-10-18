# Lab manifest (`lab.json`)

Each lab is a folder under `labs/<id>/` with a `lab.json` manifest. Its contract is [`labspec/schema/manifest.schema.json`](../labspec/schema/manifest.schema.json).

There are two consumers and one parser:
- **`bw`** reads `kit.*` to deploy, self-check and clean up;
- **the Verifier** reads `checkpoints.*` to verify submissions.

Both use `labspec` (standard library only, Python 3.9+), so they cannot interpret a lab differently.

Manifests are authored as **JSON**. YAML would need a third-party parser, and both consumers are standard-library only.

## Lint
```bash
python3 -m labspec lint labs/storage-sas-leak
python3 -m labspec lint --all labs
```
CI lints every lab on every PR. Beyond the schema, the lint rules enforce the following.

| Rule | Why |
|---|---|
| Trust level is **derived from the method**; a `trust` field is rejected | Nothing self-reported can be presented as verified (brief §11) |
| At least one Verified checkpoint (`hiddenDataset`, `externalProbe`, `artefactScan`) | Brief §4.3 |
| Verified checkpoints need `positiveControl` | Defeats "fix by deletion" (`docs/verification-methods.md` in the platform repo) |
| `externalProbe` needs Azure `hostSuffixes`, a `hostName` from `kit.names`, and `expect.status` | The prober only contacts seed-matched Azure hostnames (brief §5) |
| SAS submissions need `redactAfterUse: true`; `issuedSasUrl` needs `maxValidityMinutes <= 60` | Exception E6 (ADR-0021) |
| Every referenced file exists inside the lab folder, with no `..` and no symlinks | Kits run with Owner rights; no path tricks |
| `debrief`, datasets and questions are `private:` references and must **not** exist in the folder; files named like `*solution*`, `*answer*`, `*debrief*` or `*hidden*` are rejected | Answers never ship in the public repo (brief §11) |
| `id` equals the folder name; checkpoint IDs are unique | Stable `labId@version` references |
| `kit.scope: "none"` (nothing to deploy): no template, parameters, seed script, cleanup, names or outOfGroup; `learnerCostEstimateUsd` is 0; no `externalProbe` or `artefactScan` checkpoints. Any other scope needs `template`, `cleanup`, `names` and `outOfGroup` | Labs that bring their own data (such as a detection lab) cost nothing and can't claim to check resources that don't exist |
| `repoFile` (the file a repo submission is read from) only on `repoAtCommit` checkpoints for `hiddenDataset` or `rubricReview`; a plain path with no `.`, `..` or empty segments; a `hiddenDataset` rule must end in `.kql`. `rubricReview` defaults to `incident-note.md` | The Verifier reads exactly one named file from the learner's repo, as data |

## Seeds
Each learner gets an 8-character seed per lab (Crockford base32, shown as `K7Q2-MX4P`). `kit.names` declares the seed-derived resource names:

```json
"names": { "storageAccount": { "prefix": "bwsas", "length": 10 } }
```

`labspec.seed.derive_name(labId, seed, "storageAccount", "bwsas", 10)` returns the same value in `bw` and in the Verifier, for example `bwsas3k9x0q7m2a`.

**The seed is not a secret.** The learner sees it and the derivation is public. It identifies a submission; it does not authenticate one. The platform binds each seed to a learner server-side.

## Trust levels
| Method | Trust |
|---|---|
| `hiddenDataset`, `externalProbe`, `artefactScan` | Verified |
| `rubricReview`, `knowledgeCheck` | Reviewed |
| `selfIssuedToken` | Self-reported |
