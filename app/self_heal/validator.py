from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    ok: bool
    checks: list[dict[str, Any]]


class SelfHealValidator:
    def __init__(self, logger=None):
        self.logger = logger

    async def validate(self, action: str, payload: dict[str, Any]) -> ValidationResult:
        checks: list[dict[str, Any]] = []

        # Nesta fase é propositalmente conservador.
        # Não testa endpoints reais ainda.
        checks.append(
            {
                "name": "simulation_mode_guard",
                "ok": action in {"simulate", "pr_only", "apply_if_tests_pass", "auto_apply"},
                "details": {"action": action},
            }
        )

        ok = all(c["ok"] for c in checks)
        return ValidationResult(ok=ok, checks=checks)
