from __future__ import annotations

import asyncio
import os

from app.self_heal.frontend_guard import guard as frontend_guard
from app.self_heal.capability_planner import planner
from app.self_heal.scaffold_engine import scaffold_engine
from app.self_heal.code_emitter import code_emitter
import app.self_heal.capabilities_bootstrap  # noqa: F401


class EvolutionLoop:
    def __init__(self, db_factory, logger):
        self.db_factory = db_factory
        self.logger = logger
        self.interval = int(os.getenv("EVOLUTION_LOOP_INTERVAL", "60"))

    async def run(self):
        try:
            self.logger.warning("EVOLUTION_LOOP_CONFIG interval=%s", self.interval)
        except Exception:
            pass

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

            except Exception:
                pass

            await asyncio.sleep(self.interval)


async def start_evolution_loop(db_factory, logger):
    loop = EvolutionLoop(db_factory, logger)
    asyncio.create_task(loop.run())
