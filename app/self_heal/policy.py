from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyDecision:
    action: str
    reason: str


class SelfHealPolicy:
    def __init__(self, logger=None):
        self.logger = logger

    def decide(self, severity: str, category: str, code: str = "") -> PolicyDecision:
        severity = (severity or "LOW").upper()
        category = (category or "runtime").lower()
        code = (code or "").upper()

        if code in {"SCHEMA_MISSING_TABLE", "SCHEMA_MISSING_COLUMN"}:
            return PolicyDecision(
                action="propose_schema_patch",
                reason="known schema drift should generate a controlled schema patch proposal",
            )

        if code in {"REALTIME_DUPLICATION_RISK", "REALTIME_SCHEMA_INCOMPLETE"}:
            return PolicyDecision(
                action="simulate",
                reason="realtime issues remain simulation-only in package 03",
            )

        if severity == "CRITICAL":
            return PolicyDecision(
                action="pr_only",
                reason="critical issues require human-reviewed promotion",
            )

        if severity == "HIGH":
            return PolicyDecision(
                action="pr_only",
                reason="high severity uses supervised patch flow only",
            )

        if severity == "MEDIUM":
            return PolicyDecision(
                action="simulate",
                reason="medium severity remains simulation-first",
            )

        return PolicyDecision(
            action="ignore",
            reason="low severity informational only",
        )
