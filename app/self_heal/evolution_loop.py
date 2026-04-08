from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from typing import Any, Callable

from .detector import SelfHealDetector
from .classifier import SelfHealClassifier
from .policy import SelfHealPolicy
from .validator import SelfHealValidator
from .runtime_patch_engine import RuntimePatchEngine


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


class EvolutionLoop:
    def __init__(self, db_factory: Callable[[], Any] | None = None, logger=None):
        self.db_factory = db_factory
        self.logger = logger
        self.enabled = _env_bool("ENABLE_EVOLUTION_LOOP", False)
        self.interval = _env_int("EVOLUTION_LOOP_INTERVAL", 60)

        self.classifier = SelfHealClassifier(logger=logger)
        self.policy = SelfHealPolicy(logger=logger)
        self.validator = SelfHealValidator(logger=logger)
        self.patch_engine = RuntimePatchEngine(logger=logger)

        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if not self.enabled:
            self._log("EVOLUTION_LOOP_DISABLED")
            return

        if self._running:
            self._log("EVOLUTION_LOOP_ALREADY_RUNNING")
            return

        self._running = True
        self._task = asyncio.create_task(self._run(), name="evolution-loop")
        self._log("EVOLUTION_LOOP_STARTED", interval=self.interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._log("EVOLUTION_LOOP_STOPPED")

    async def _run(self) -> None:
        self._log("SELF_HEAL_DETECTOR_READY")
        self._log("SELF_HEAL_CLASSIFIER_READY")
        self._log("SELF_HEAL_POLICY_READY")
        self._log("SELF_HEAL_VALIDATOR_READY")

        while self._running:
            try:
                await self._tick()
            except Exception as exc:
                self._log("EVOLUTION_LOOP_TICK_ERROR", error=repr(exc))

            await asyncio.sleep(self.interval)

    async def _tick(self) -> None:
        db = None
        try:
            if self.db_factory:
                db = self.db_factory()

            detector = SelfHealDetector(db=db, logger=self.logger)

            findings = await detector.scan()
            raw_findings = detector.serialize(findings)

            if not raw_findings:
                self._log("EVOLUTION_LOOP_NO_FINDINGS")
                return

            classified = self.classifier.classify(raw_findings)

            for issue in classified:
                decision = self.policy.decide(issue.severity, issue.category, issue.code)
                bundle = await self.patch_engine.build_patch_bundle(issue, decision)
                validation = await self.validator.validate(decision.action, bundle)

                self._route_action(issue, decision, bundle, validation, db)
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def _route_action(self, issue, decision, bundle, validation, db=None) -> None:
        self._log(
            "EVOLUTION_LOOP_DECISION",
            issue=issue.code,
            severity=issue.severity,
            category=issue.category,
            action=decision.action,
            validation_ok=validation.ok,
            details=getattr(issue, "details", {}),
        )

        if not validation.ok:
            self._log(
                "EVOLUTION_LOOP_ACTION_SKIPPED",
                issue=issue.code,
                reason="validation_failed",
            )
            return

        if decision.action == "ignore":
            self._log("EVOLUTION_LOOP_IGNORED", issue=issue.code)
            return

        if decision.action == "simulate":
            self._log("EVOLUTION_LOOP_SIMULATED", issue=issue.code, bundle=bundle)
            return

        if decision.action == "pr_only":
            self._log("EVOLUTION_LOOP_PR_ONLY", issue=issue.code, bundle=bundle)
            return

        if decision.action == "propose_schema_patch":
            self._log("EVOLUTION_LOOP_SCHEMA_PATCH_PROPOSED", issue=issue.code, bundle=bundle)
            return

        self._log("EVOLUTION_LOOP_UNKNOWN_ACTION", issue=issue.code, action=decision.action)

    def _log(self, message: str, **kwargs: Any) -> None:
        if self.logger:
            try:
                self.logger.info(message, extra=kwargs)
                return
            except Exception:
                pass

        print({"message": message, **kwargs})


_loop_singleton: EvolutionLoop | None = None


async def start_evolution_loop(db_factory=None, logger=None) -> EvolutionLoop:
    global _loop_singleton

    if _loop_singleton is None:
        _loop_singleton = EvolutionLoop(db_factory=db_factory, logger=logger)

    await _loop_singleton.start()
    return _loop_singleton
