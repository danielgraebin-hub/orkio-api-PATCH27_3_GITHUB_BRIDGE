from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Detection:
    code: str
    severity_hint: str
    source: str
    details: dict[str, Any]


class SelfHealDetector:
    def __init__(self, db=None, logger=None):
        self.db = db
        self.logger = logger

    async def scan(self) -> list[Detection]:
        findings: list[Detection] = []

        findings.extend(await self._scan_schema_health())
        findings.extend(await self._scan_runtime_health())
        findings.extend(await self._scan_realtime_health())
        findings.extend(await self._scan_endpoint_health())

        return findings

    async def _scan_schema_health(self) -> list[Detection]:
        findings: list[Detection] = []

        # Placeholder seguro:
        # aqui depois entram scans reais de missing_table / missing_column / index drift
        return findings

    async def _scan_runtime_health(self) -> list[Detection]:
        findings: list[Detection] = []

        # Placeholder seguro:
        # aqui depois entram runtime exceptions classificáveis e incident signatures
        return findings

    async def _scan_realtime_health(self) -> list[Detection]:
        findings: list[Detection] = []

        # Placeholder seguro:
        # futura detecção de duplicidade response.text.done + response.audio_transcript.final
        return findings

    async def _scan_endpoint_health(self) -> list[Detection]:
        findings: list[Detection] = []

        # Placeholder seguro:
        # futura checagem de contratos /api/chat /api/realtime/start /api/realtime/end
        return findings

    def serialize(self, findings: list[Detection]) -> list[dict[str, Any]]:
        return [asdict(f) for f in findings]
