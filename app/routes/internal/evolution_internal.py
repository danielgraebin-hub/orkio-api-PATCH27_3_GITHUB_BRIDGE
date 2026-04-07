from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .schema_patch_engine import classify_and_patch

router = APIRouter(prefix="/api/internal/evolution", tags=["evolution-internal"])


def _clean_env(name: str, default: str = "") -> str:
    v = os.getenv(name, default) or default
    v = str(v).strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        v = v[1:-1].strip()
    return v


def _base_url() -> str:
    return _clean_env("INTERNAL_API_BASE", "http://127.0.0.1:8080").rstrip("/")


def _default_branch() -> str:
    return _clean_env("GITHUB_BRANCH", "main") or "main"


def _safe_branch_name(table_name: str) -> str:
    stamp = int(time.time())
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in (table_name or "unknown"))
    return f"selfheal/schema-{safe}-{stamp}"


def _request(method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        resp = requests.request(method, url, json=json_body, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"internal request failed: {e}")

    try:
        detail: Any = resp.json()
    except Exception:
        detail = {"raw": resp.text}

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=detail)

    if isinstance(detail, dict):
        return detail
    return {"data": detail}


def _build_db_patch(current_content: str, sql_patch: str, table_name: str) -> str:
    marker = "def _reconcile_self_heal_schema_boot():"
    if marker in current_content:
        return current_content

    bootstrap = f"""

def _reconcile_self_heal_schema_boot():
    if ENGINE is None:
        return
    try:
        with ENGINE.begin() as conn:
            conn.execute(text(\"\"\"
{sql_patch.strip()}
\"\"\"))
        print(\"SELF_HEAL_SCHEMA_BOOT_OK table={table_name}\")
    except Exception as e:
        print(\"SELF_HEAL_SCHEMA_BOOT_FAILED table={table_name}\", str(e))
"""

    call_marker = "_reconcile_files_schema_boot()"
    if call_marker in current_content:
        return current_content.replace(
            call_marker,
            f"_reconcile_self_heal_schema_boot()\\n{call_marker}",
            1
        ) + bootstrap

    return current_content + bootstrap + "\\n\\n_reconcile_self_heal_schema_boot()\\n"


class EvolutionClassifyIn(BaseModel):
    error_text: str = Field(min_length=3, max_length=20000)


class EvolutionProposeIn(BaseModel):
    error_text: str = Field(min_length=3, max_length=20000)
    path: str = Field(default="app/db.py", min_length=1, max_length=300)
    source_branch: Optional[str] = Field(default=None, max_length=120)
    auto_pr: bool = Field(default=True)
    pr_title: Optional[str] = Field(default=None, max_length=200)
    pr_body: Optional[str] = Field(default=None, max_length=20000)


@router.get("/health")
def evolution_health():
    return {
        "ok": True,
        "service": "evolution_internal",
        "mode": "safe_pr",
        "git_bridge_base": _base_url(),
        "default_branch": _default_branch(),
    }


@router.post("/classify")
def evolution_classify(payload: EvolutionClassifyIn):
    result = classify_and_patch(payload.error_text)
    return {
        "ok": True,
        "classification": result,
    }


@router.post("/propose-schema-patch")
def evolution_propose_schema_patch(payload: EvolutionProposeIn):
    result = classify_and_patch(payload.error_text)

    if result.get("action") != "create_table_patch":
        return {
            "ok": False,
            "classification": result,
            "reason": "no_supported_patch_generated",
        }

    table_name = result["table"]
    sql_patch = result["sql"]
    branch_name = _safe_branch_name(table_name)
    source_branch = payload.source_branch or _default_branch()

    current_file = _request("GET", f"/api/internal/git/file?path={payload.path}&branch={source_branch}")
    current_content = current_file.get("content", "")
    if not isinstance(current_content, str):
        raise HTTPException(status_code=500, detail="git file content missing")

    patched_content = _build_db_patch(current_content, sql_patch, table_name)
    patch_hash = hashlib.sha256((payload.path + sql_patch).encode("utf-8")).hexdigest()[:12]

    branch_resp = _request(
        "POST",
        "/api/internal/git/branch",
        json_body={
            "branch_name": branch_name,
            "source_branch": source_branch,
        },
    )

    commit_message = f"fix(self-heal): reconcile missing table {table_name} [{patch_hash}]"
    commit_resp = _request(
        "POST",
        "/api/internal/git/commit",
        json_body={
            "path": payload.path,
            "content": patched_content,
            "message": commit_message,
            "branch": branch_name,
        },
    )

    pr_resp = None
    if payload.auto_pr:
        pr_title = payload.pr_title or f"Self-heal: reconcile missing table `{table_name}`"
        pr_body = payload.pr_body or (
            f"Automated safe-mode schema patch.\\n\\n"
            f"- detected table: `{table_name}`\\n"
            f"- action: `{result['action']}`\\n"
            f"- path: `{payload.path}`\\n"
            f"- source branch: `{source_branch}`\\n"
            f"- generated by: `evolution_internal`\\n\\n"
            f"Review required before merge."
        )
        pr_resp = _request(
            "POST",
            "/api/internal/git/pr",
            json_body={
                "title": pr_title,
                "body": pr_body,
                "head": branch_name,
                "base": source_branch,
            },
        )

    return {
        "ok": True,
        "mode": "safe_pr",
        "classification": result,
        "branch": branch_resp,
        "commit": commit_resp,
        "pr": pr_resp,
    }
