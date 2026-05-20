#!/usr/bin/env python3
"""Cloud Region targets: 6 corp backends + 4 stores (4 native tenants).

The acquired-tenant store (store-de-berlin-01) is NOT created here — it's
created live during the M5 demo via the 'Acquire Crusty Croissant' runbook.

Cloud Region targets are stand-ins for real infrastructure: they accept
deployments without connecting to anything. Deployment steps are mock
scripts that log what they would have done.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import octopus_api as o

TARGETS = [
    # Corporate backends — Cloud-Prod env, untenanted
    {"Name": "corp-pos-backend",      "Envs": ["Cloud-Prod"],
     "Roles": ["corp-backend"], "Tenant": None,
     "Region": "us-east-1",
     "Description": "POS backend (corp). Mock cloud-region target."},
    {"Name": "corp-payments-backend", "Envs": ["Cloud-Prod"],
     "Roles": ["corp-backend"], "Tenant": None,
     "Region": "us-east-1",
     "Description": "Payment gateway backend (corp). Mock."},
    {"Name": "corp-mobile-api",       "Envs": ["Cloud-Prod"],
     "Roles": ["corp-backend"], "Tenant": None,
     "Region": "us-east-1",
     "Description": "Mobile-ordering API backend (corp). Mock."},
    {"Name": "corp-loyalty",          "Envs": ["Cloud-Prod"],
     "Roles": ["corp-backend"], "Tenant": None,
     "Region": "us-east-1",
     "Description": "Loyalty-rewards backend (corp). Mock."},
    {"Name": "corp-marketing",        "Envs": ["Cloud-Prod"],
     "Roles": ["corp-backend"], "Tenant": None,
     "Region": "us-east-1",
     "Description": "Marketing / promo engine backend (corp). Mock."},
    {"Name": "corp-pci-vault",        "Envs": ["Cloud-Prod", "Cloud-Prod-BreakGlass"],
     "Roles": ["corp-backend", "permanent-break-glass-only"], "Tenant": None,
     "Region": "us-east-1",
     "Description": "PCI cardholder-data vault (corp). Reachable from both Cloud-Prod (frozen) and Cloud-Prod-BreakGlass (break-glass channel routes here). Tag 'permanent-break-glass-only' is signaling only."},

    # Store targets — Markets env, each tenanted to one native tenant
    {"Name": "store-nz-auckland-01",  "Envs": ["Markets"], "Roles": ["store"],
     "Tenant": "MMI-NZ-Auckland", "Region": "ap-southeast-2",
     "Description": "NZ Auckland store #01 (mock)."},
    {"Name": "store-au-sydney-01",    "Envs": ["Markets"], "Roles": ["store"],
     "Tenant": "MMI-AU-Sydney", "Region": "ap-southeast-2",
     "Description": "AU Sydney store #01 (mock)."},
    {"Name": "store-uk-london-01",    "Envs": ["Markets"], "Roles": ["store"],
     "Tenant": "MMI-UK-London", "Region": "eu-west-2",
     "Description": "UK London store #01 (mock)."},
    {"Name": "store-us-newyork-01",   "Envs": ["Markets"], "Roles": ["store"],
     "Tenant": "MMI-US-NewYork", "Region": "us-east-1",
     "Description": "US New York store #01 (mock)."},
]


def ensure_target(t_def: dict, foundation: dict, tenants: dict) -> dict:
    existing = o.find_by_name("/machines", t_def["Name"])
    env_ids = [foundation["environments"][n] for n in t_def["Envs"]]
    tenant_ids = [tenants[t_def["Tenant"]]] if t_def["Tenant"] else []
    is_tenanted = bool(tenant_ids)

    endpoint = {
        "CommunicationStyle": "None",
        "DefaultWorkerPoolId": "",
        "Container": {"Image": None, "FeedId": None},
    }

    body = {
        "Name": t_def["Name"],
        "Status": "Unknown",
        "EnvironmentIds": env_ids,
        "Roles": t_def["Roles"],
        "TenantIds": tenant_ids,
        "TenantTags": [],
        "TenantedDeploymentParticipation": "Tenanted" if is_tenanted else "Untenanted",
        "MachinePolicyId": None,
        "Thumbprint": None,
        "Uri": None,
        "IsDisabled": False,
        "Endpoint": endpoint,
        "OperatingSystem": "Unknown",
        "ShellName": "Unknown",
        "ShellVersion": "Unknown",
    }

    if existing:
        # Preserve immutable fields, merge mutable ones
        existing["EnvironmentIds"] = env_ids
        existing["Roles"] = t_def["Roles"]
        existing["TenantIds"] = tenant_ids
        existing["TenantedDeploymentParticipation"] = body["TenantedDeploymentParticipation"]
        updated = o.put(f"/machines/{existing['Id']}", existing)
        o.ok(f"target updated: {t_def['Name']} ({existing['Id']}) envs={t_def['Envs']}")
        return updated

    created = o.post("/machines", body)
    o.ok(f"created target: {created['Name']} ({created['Id']}) envs={t_def['Envs']} tenant={t_def['Tenant']}")
    return created


def main() -> None:
    foundation = o.load_ids("foundation-ids.json")
    tenants = o.load_ids("tenants.json")["tenants"]

    target_ids: dict[str, str] = {}
    for t_def in TARGETS:
        t = ensure_target(t_def, foundation, tenants)
        target_ids[t["Name"]] = t["Id"]

    o.save_ids("targets.json", {"targets": target_ids})


if __name__ == "__main__":
    main()
