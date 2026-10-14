#!/usr/bin/env bash
# Lab 0 cleanup removes your playground guardrails, budget and tag. You normally KEEP them while doing
# other labs; run this only when you are finished with Bastionworks in this subscription.
set -euo pipefail
exec python3 -m bw cleanup lab-0
