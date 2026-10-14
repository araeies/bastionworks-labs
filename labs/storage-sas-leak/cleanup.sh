#!/usr/bin/env bash
# Removes everything this lab created (the resource group and all it contains).
set -euo pipefail
exec python3 -m bw cleanup storage-sas-leak
