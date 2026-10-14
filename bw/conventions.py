"""Names and tags every kit uses, so bw status / cleanup can find everything a lab created."""

PLAYGROUND_LAB = "lab-0"  # the lab that creates the playground tag, budget and guardrails
PLAYGROUND_TAG = "bastionworks:playground"  # subscription tag set by Lab 0; bw refuses to deploy without it
LAB_TAG = "bastionworks:lab"  # lab id, on every resource group and resource a kit creates
SEED_TAG = "bastionworks:seed"
KIT_TAG = "bastionworks:kit"  # labId@version
EXPIRES_TAG = "bastionworks:expires"  # ISO date; bw status warns after it

# Objects that cannot carry Azure tags record their owner here instead:
#  - role assignments: description = "bastionworks:<labId>:<seed>"
#  - Entra app registrations: tags include "bastionworks:<labId>"
#  - policy assignments: metadata.bastionworksLab = <labId>
#  - budgets: name starts with "bw-<labId>-budget-"
DESCRIPTION_PREFIX = "bastionworks:"


def resource_group_name(lab_id: str, seed: str) -> str:
    return f"rg-bw-{lab_id}-{seed.lower()}"


def owner_marker(lab_id: str) -> str:
    return f"{DESCRIPTION_PREFIX}{lab_id}"
