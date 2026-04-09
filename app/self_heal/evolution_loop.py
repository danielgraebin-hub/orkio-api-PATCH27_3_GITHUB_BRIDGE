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


def _clean_env(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    if not s:
        return default
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s


def _env_bool(name: str, default: bool = False) -> bool:
    value = _clean_env(os.getenv(name, str(default))).lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _clean_env(os.getenv(name, str(default)))
    try:
        return int(raw)
    except ValueError:
        return default


class EvolutionLoop:
    def __init__(self, db_factory: Callable[[], Any] | None = None, logger=None):
        self.db_factory = db_factory
        self.logger = logger

        raw_enabled = os.getenv("ENABLE_EVOLUTION_LOOP", None)
        parsed_enabled = _env_bool("ENABLE_EVOLUTION_LOOP", False)
        force_enabled = _env_bool("FORCE_ENABLE_EVOLUTION_LOOP", False)

        self.enabled = bool(parsed_enabled or force_enabled)
        self.interval = _env_int("EVOLUTION_LOOP_INTERVAL", 60)

        self.classifier = SelfHealClassifier(logger=logger)
        self.policy = SelfHealPolicy(logger=logger)
        self.validator = SelfHealValidator(logger=logger)
        self.patch_engine = RuntimePatchEngine(logger=logger)

        self._task: asyncio.Task | None = None
        self._running = False

        self._log(
            "EVOLUTION_LOOP_CONFIG",
            raw_enable_value=raw_enabled,
            parsed_enable_value=parsed_enabled,
            force_enable_value=force_enabled,
            final_enabled=self.enabled,
            interval=self.interval,
        )

    async def start(self) -> None:
        if not self.enabled:
            self._log("EVOLUTION_LOOP_DISABLED", interval=self.interval)
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
            self._trigger_schema_patch(issue, bundle)
            return

        self._log("EVOLUTION_LOOP_UNKNOWN_ACTION", issue=issue.code, action=decision.action)

    def _trigger_schema_patch(self, issue, bundle) -> None:
        try:
            from app.routes.internal.evolution_trigger import maybe_trigger_schema_patch
        except Exception as exc:
            self._log(
                "EVOLUTION_PATCH_TRIGGER_IMPORT_FAIL",
                error=repr(exc),
                issue=issue.code,
            )
            return

        try:
            maybe_trigger_schema_patch(
                issue_code=issue.code,
                details=getattr(issue, "details", {}),
                source="self_heal_loop",
            )

            self._log(
                "EVOLUTION_PATCH_TRIGGER_SENT",
                issue=issue.code,
                details=getattr(issue, "details", {}),
            )

        except Exception as exc:
            self._log(
                "EVOLUTION_PATCH_TRIGGER_FAILED",
                issue=issue.code,
                error=repr(exc),
            )

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
