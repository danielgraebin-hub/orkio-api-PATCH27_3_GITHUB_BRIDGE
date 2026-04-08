from __future__ import annotations

from dataclasses import asdict
from typing import Any


class RuntimePatchEngine:
    def __init__(self, logger=None):
        self.logger = logger

    async def build_patch_bundle(self, issue, decision) -> dict[str, Any]:
        bundle = {
            "issue": asdict(issue),
            "decision": asdict(decision),
            "mode": "simulation-first",
            "proposed_actions": self._proposed_actions(issue, decision),
        }
        return bundle

    def _proposed_actions(self, issue, decision) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        category = getattr(issue, "category", "runtime")
        code = getattr(issue, "code", "UNKNOWN")

        if category == "schema":
            actions.append(
                {
                    "type": "schema_reconcile_candidate",
                    "code": code,
                    "safe": False,
                    "note": "candidate only in package 01",
                }
            )
        elif category == "realtime":
            actions.append(
                {
                    "type": "realtime_guard_candidate",
                    "code": code,
                    "safe": False,
                    "note": "candidate only in package 01",
                }
            )
        else:
            actions.append(
                {
                    "type": "runtime_investigation_candidate",
                    "code": code,
                    "safe": False,
                    "note": "candidate only in package 01",
                }
            )

        return actions
