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
