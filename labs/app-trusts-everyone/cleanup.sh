#!/usr/bin/env bash
# Removes everything this lab created (the resource group and all it contains). Your Entra app registration
# for built-in auth is yours: delete it in Entra ID > App registrations if you no longer need it.
set -euo pipefail
exec python3 -m bw cleanup app-trusts-everyone
