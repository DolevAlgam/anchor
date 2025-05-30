from typing import Dict, Any


def plan_stats(plan_json: Dict[str, Any]) -> Dict[str, int]:
    """Return counts of add/change/destroy from plan JSON."""
    if "resource_changes" not in plan_json:
        return {}
    adds = changes = destroys = 0
    for rc in plan_json["resource_changes"]:
        action = rc.get("change", {}).get("actions", [])
        if "create" in action:
            adds += 1
        if "update" in action:
            changes += 1
        if "delete" in action:
            destroys += 1
    return {"create": adds, "update": changes, "delete": destroys} 