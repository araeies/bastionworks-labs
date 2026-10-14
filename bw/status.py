"""bw status: every Bastionworks resource still running, with its recent daily cost (brief §4.1)."""

import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, TextIO

from bw.az import Az, AzError
from bw.conventions import EXPIRES_TAG, LAB_TAG

COST_API_VERSION = "2023-11-01"


def _daily_cost_by_group(az: Az, subscription_id: str, today: date) -> Optional[Dict[str, float]]:
    """Yesterday's actual cost per resource group. Cost data lags by up to a day; None if unavailable."""
    yesterday = today - timedelta(days=1)
    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": f"{yesterday.isoformat()}T00:00:00Z", "to": f"{yesterday.isoformat()}T23:59:59Z"},
        "dataset": {
            "granularity": "None",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ResourceGroupName"}],
        },
    }
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}"
        f"/providers/Microsoft.CostManagement/query?api-version={COST_API_VERSION}"
    )
    try:
        result = az.run(["rest", "--method", "post", "--url", url, "--body", json.dumps(body)])
    except AzError:
        return None
    properties = (result or {}).get("properties") or {}
    names = [c.get("name") for c in properties.get("columns") or []]
    if "Cost" not in names or "ResourceGroupName" not in names:
        return None
    cost_i, group_i = names.index("Cost"), names.index("ResourceGroupName")
    return {str(row[group_i]).lower(): float(row[cost_i]) for row in properties.get("rows") or []}


def run_status(az: Az, out: TextIO, today: Optional[date] = None) -> int:
    today = today or date.today()
    account = az.run(["account", "show"])
    groups: List[Dict[str, Any]] = [g for g in az.run(["group", "list"]) or [] if LAB_TAG in (g.get("tags") or {})]
    resources = [r for r in az.run(["resource", "list"]) or [] if LAB_TAG in (r.get("tags") or {})]

    if not groups and not resources:
        print(f"\nNo Bastionworks lab resources are running in {account['name']}.", file=out)
        return 0

    by_group: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for resource in resources:
        by_group[str(resource.get("resourceGroup", "")).lower()].append(resource)
    costs = _daily_cost_by_group(az, account["id"], today)

    print(f"\nBastionworks resources in {account['name']}:", file=out)
    for group in sorted(groups, key=lambda g: g["name"]):
        tags = group.get("tags") or {}
        expires = tags.get(EXPIRES_TAG, "?")
        overdue = expires != "?" and expires < today.isoformat()
        cost = "cost n/a (lags up to 24h)" if costs is None else f"${costs.get(group['name'].lower(), 0.0):.2f} yesterday"
        flag = "  ← EXPIRED: run bw cleanup" if overdue else ""
        print(f"\n  {group['name']}  lab={tags.get(LAB_TAG)}  expires={expires}  {cost}{flag}", file=out)
        for resource in by_group.get(group["name"].lower(), []):
            print(f"    - {resource['type']}  {resource['name']}", file=out)
    print("\nWhen you have verified a lab, run: bw cleanup <lab>", file=out)
    return 0
