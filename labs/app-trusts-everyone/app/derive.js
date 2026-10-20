// The same seed derivation as labspec.seed.derive_token (Python), so the app and the Verifier agree on this
// learner's values. A seed identifies; it isn't a secret, and neither is anything derived from it.
// tests/test_lab2_app.py pins this against the Python implementation.
"use strict";

const { createHash } = require("node:crypto");

const ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz";

function deriveToken(labId, seed, purpose, length = 24) {
  const digest = createHash("sha256").update(`bastionworks/v1/${labId}/${seed}/${purpose}`, "ascii").digest("hex");
  let number = BigInt(`0x${digest}`);
  let out = "";
  for (let i = 0; i < length; i++) {
    out += ALPHABET[Number(number % 36n)];
    number /= 36n;
  }
  return out;
}

/** labspec.knowledge.expected_token: the self-reported token for one checkpoint. */
const expectedToken = (labId, seed, checkpointId) => `bwt-${deriveToken(labId, seed, `token-${checkpointId}`)}`;

module.exports = { deriveToken, expectedToken };
