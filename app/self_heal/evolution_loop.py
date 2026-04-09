from __future__ import annotations

import asyncio
import os

from app.self_heal.frontend_guard import guard as frontend_guard
from app.self_heal.capability_planner import planner
from app.self_heal.scaffold_engine import scaffold_engine
from app.self_heal.code_emitter import code_emitter
from app.self_heal.github_bridge_executor import GitHubBridgeExecutor
from app.self_heal.github_pr_writer import pr_writer
import app.self_heal.capabilities_bootstrap  # noqa: F401

github_bridge = GitHubBridgeExecutor()


def _env_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


class EvolutionLoop:
    def __init__(self, db_factory, logger):
        self.db_factory = db_factory
        self.logger = logger
        self.interval = int(os.getenv("EVOLUTION_LOOP_INTERVAL", "60"))
        self.enabled = _env_true("ENABLE_EVOLUTION_LOOP", "false") or _env_true("FORCE_ENABLE_EVOLUTION_LOOP", "false")
        self.allow_bridge_execute = _env_true("AUTO_PR_EXECUTION_ENABLED", "false")
        self.allow_pr_write = _env_true("AUTO_PR_WRITE_ENABLED", "false")

    async def run(self):
        try:
            self.logger.warning("EVOLUTION_LOOP_CONFIG interval=%s", self.interval)
        except Exception:
            pass

        if not self.enabled:
            try:
                self.logger.warning("EVOLUTION_LOOP_DISABLED approval_gate=env")
            except Exception:
                pass
            return

        try:
            self.logger.warning("EVOLUTION_LOOP_STARTED")
        except Exception:
            pass

        while True:
            try:
                self.logger.warning("SELF_HEAL_DETECTOR_READY")
                self.logger.warning("SELF_HEAL_CLASSIFIER_READY")
                self.logger.warning("SELF_HEAL_POLICY_READY")
                self.logger.warning("SELF_HEAL_VALIDATOR_READY")

                try:
                    frontend_guard.analyze_contract_mismatch(
                        endpoint="realtime_stream",
                        expected_schema={"transcript": "string"},
                        received_schema={"transcript": "string"},
                    )
                except Exception:
                    pass

                try:
                    planner.build_execution_plan("self_knowledge_app")
                except Exception:
                    pass

                try:
                    scaffold_engine.generate_blueprint("self_knowledge_app")
                except Exception:
                    pass

                try:
                    code_emitter.emit_code_plan("self_knowledge_app")
                except Exception:
                    pass

                if self.allow_bridge_execute:
                    try:
                        github_bridge.execute("self_knowledge_app")
                    except Exception:
                        pass

                if self.allow_pr_write:
                    try:
                        pr_writer.execute("self_knowledge_app")
                    except Exception:
                        pass

            except Exception:
                pass

            await asyncio.sleep(self.interval)


async def start_evolution_loop(db_factory, logger):
    loop = EvolutionLoop(db_factory, logger)
    if not loop.enabled:
        try:
            logger.warning("EVOLUTION_LOOP_START_SKIPPED approval_gate=env")
        except Exception:
            pass
        return
    asyncio.create_task(loop.run())
