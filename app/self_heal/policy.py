from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyDecision:
    action: str  # ignore | simulate | auto_apply | apply_if_tests_pass | pr_only
    reason: str


class SelfHealPolicy:
    def __init__(self, logger=None):
        self.logger = logger

    def decide(self, severity: str, category: str) -> PolicyDecision:
        severity = severity.upper()

        if severity == "CRITICAL":
            return PolicyDecision(
                action="pr_only",
                reason="critical issues require human-supervised promotion",
            )

        if severity == "HIGH":
            return PolicyDecision(
                action="apply_if_tests_pass",
                reason="high severity requires validation gate before any action",
            )

        if severity == "MEDIUM":
            return PolicyDecision(
                action="simulate",
                reason="medium severity stays in simulation-first mode for now",
            )

        return PolicyDecision(
            action="simulate",
            reason="low severity stays in simulation-first mode for now",
        )
