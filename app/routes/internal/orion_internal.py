from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .git_internal import (
    BranchCreateIn,
    CommitFileIn,
    PullRequestIn,
    git_commit_file,
    git_create_branch,
    git_file,
    git_health,
    git_open_pr,
    git_search,
    git_tree,
)

router = APIRouter(prefix="/api/internal/orion", tags=["orion-internal"])

_PATCH_APPROVAL_MARKERS = (
    "de acordo",
    "aprovado",
    "autorizado",
    "pode seguir",
    "ok, executar",
    "ok executar",
    "liberado",
)

_DEPLOY_APPROVAL_MARKERS = (
    "autorizo deploy",
    "deploy autorizado",
    "pode promover para produção",
    "pode promover para producao",
    "autorizo produção",
    "autorizo producao",
)

_GITHUB_KEYWORDS = (
    "github",
    "repo",
    "repositório",
    "repositorio",
    "branch",
    "ramo",
    "commit",
    "pull request",
    "pr ",
    "arquivo",
    "file ",
    "código",
    "codigo",
    "crie",
    "criar",
    "novo arquivo",
    "main",
)

_MAIN_OVERRIDE_MARKERS = (
    "diretamente na main",
    "na branch main",
    "na main",
    "commit na main",
    "aplique na main",
    "escreva na main",
    "salve na main",
)


class OrionGitWriteIn(BaseModel):
    path: str = Field(min_length=1)
    content: str = Field(min_length=1)
    commit_message: str = Field(min_length=3, max_length=300)
    branch: Optional[str] = Field(default=None, max_length=120)
    base_branch: Optional[str] = Field(default=None, max_length=120)
    open_pr: bool = True


class OrionBranchCreateIn(BaseModel):
    branch_name: str = Field(min_length=2, max_length=120)
    source_branch: Optional[str] = None


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip().strip('"').strip("'")


def is_orion_agent_name(name: Optional[str]) -> bool:
    s = (name or "").strip().lower()
    return s.startswith("orion")


def has_github_intent(message: str) -> bool:
    s = (message or "").lower()
    return any(k in s for k in _GITHUB_KEYWORDS)


def has_explicit_patch_approval(message: str) -> bool:
    s = (message or "").lower()
    return any(k in s for k in _PATCH_APPROVAL_MARKERS)


def has_explicit_deploy_approval(message: str) -> bool:
    s = (message or "").lower()
    return any(k in s for k in _DEPLOY_APPROVAL_MARKERS) or ("deploy" in s and "produção" in s) or ("deploy" in s and "producao" in s)


def has_explicit_main_override(message: str) -> bool:
    s = (message or "").lower()
    approval = any(k in s for k in _PATCH_APPROVAL_MARKERS)
    wants_main = any(k in s for k in _MAIN_OVERRIDE_MARKERS)
    return approval and wants_main


def _extract_branch(message: str) -> Optional[str]:
    s = message or ""
    patterns = [
        r"(?:branch|ramo)\s*[:=]\s*([A-Za-z0-9_./\-]{2,120})",
        r"(?:na|no)\s+branch\s+([A-Za-z0-9_./\-]{2,120})",
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_path(message: str) -> Optional[str]:
    s = message or ""
    fenced = re.findall(r"`([^`]+)`", s)
    for item in fenced:
        item = item.strip()
        if "/" in item and "." in item and " " not in item:
            return item
    patterns = [
        r"(?:arquivo|file|path|caminho)\s*[:=]\s*([A-Za-z0-9_./\-]+\.[A-Za-z0-9_]+)",
        r"([A-Za-z0-9_./\-]+\.[A-Za-z0-9_]+)",
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if "/" in candidate or candidate.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml", ".sql", ".css", ".html", ".txt")):
                return candidate
    return None


def _extract_search_query(message: str) -> Optional[str]:
    s = (message or "").strip()
    quoted = re.findall(r'"([^"]+)"', s)
    if quoted:
        return quoted[0].strip()
    quoted = re.findall(r"'([^']+)'", s)
    if quoted:
        return quoted[0].strip()
    m = re.search(r"(?:buscar|busque|procure|pesquise|search)\s+(.+)", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()[:180]
    return None


def _extract_content_literal(message: str) -> Optional[str]:
    s = message or ""
    code_blocks = re.findall(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]*?)```", s)
    if code_blocks:
        return code_blocks[0].strip()

    quoted = re.search(r'conte[uú]do\s*[:=]\s*"([\s\S]+)"', s, flags=re.IGNORECASE)
    if quoted:
        return quoted.group(1).strip()
    quoted = re.search(r"conte[uú]do\s*[:=]\s*'([\s\S]+)'", s, flags=re.IGNORECASE)
    if quoted:
        return quoted.group(1).strip()

    m = re.search(r'com\s+conte[uú]do\s+"([\s\S]+)"', s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"com\s+conte[uú]do\s+'([\s\S]+)'", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    m = re.search(r'com\s+conte[uú]do\s*[:=]?\s*([\s\S]+)$', s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _extract_branch_create_name(message: str) -> Optional[str]:
    s = message or ""
    patterns = [
        r"(?:crie|criar|abra|gerar)\s+(?:uma\s+)?branch\s+(?:chamada\s+)?([A-Za-z0-9_./\-]{2,120})",
        r"(?:crie|criar|abra|gerar)\s+(?:um\s+)?ramo\s+(?:chamado\s+)?([A-Za-z0-9_./\-]{2,120})",
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _looks_like_create_branch(message: str) -> bool:
    low = (message or "").lower()
    return ("branch" in low or "ramo" in low) and any(k in low for k in ("crie", "criar", "abra", "gerar"))


def _looks_like_create_file(message: str) -> bool:
    low = (message or "").lower()
    return any(k in low for k in ("crie", "criar", "novo arquivo", "adicione arquivo")) and any(k in low for k in ("arquivo", "file"))


def resolve_orion_github_operation(message: str) -> Dict[str, Any]:
    s = (message or "").strip()
    low = s.lower()
    if not has_github_intent(low):
        return {"kind": "none"}

    branch = _extract_branch(s)
    path = _extract_path(s)

    if any(k in low for k in ("acesso", "access", "health", "status", "conect")):
        return {"kind": "health", "branch": branch}
    if any(k in low for k in ("árvore", "arvore", "tree", "listar repo", "listar reposit", "liste o repo", "listar arquivos")):
        return {"kind": "tree", "branch": branch}
    if _looks_like_create_branch(s):
        return {
            "kind": "create_branch",
            "branch_name": _extract_branch_create_name(s),
            "source_branch": _env("GITHUB_BRANCH", "main"),
        }
    if path and _looks_like_create_file(s):
        return {
            "kind": "create_file",
            "branch": branch,
            "path": path,
            "content": _extract_content_literal(s) or "",
        }
    if any(k in low for k in ("corrija", "corrigir", "ajuste", "ajustar", "aplique", "aplicar", "fix", "patch")) and path:
        return {"kind": "write_fix", "branch": branch, "path": path}
    if path and any(k in low for k in ("arquivo", "file", "ler", "abra", "mostrar", "mostre", "analise")):
        return {"kind": "file", "branch": branch, "path": path}

    search_query = _extract_search_query(s)
    if search_query:
        return {"kind": "search", "branch": branch, "query": search_query}

    if path:
        return {"kind": "file", "branch": branch, "path": path}
    return {"kind": "tree", "branch": branch}


def run_orion_github_read(op: Dict[str, Any]) -> Dict[str, Any]:
    kind = (op or {}).get("kind")
    if kind == "health":
        return git_health()
    if kind == "tree":
        return git_tree(branch=op.get("branch"))
    if kind == "file":
        return git_file(path=str(op.get("path") or ""), branch=op.get("branch"))
    if kind == "search":
        return git_search(query=str(op.get("query") or ""), branch=op.get("branch"))
    raise HTTPException(status_code=400, detail=f"Unsupported Orion GitHub read op: {kind}")


def create_orion_branch_name(path: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9/_\-.]+", "-", (path or "change").strip().lower()).strip("-")
    cleaned = cleaned.replace("/", "-").replace("_", "-").replace(".", "-")
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")[:48] or "change"
    return f"orion-fix/{cleaned}-{int(time.time())}"


def resolve_target_branch_for_write(message: str, path: str, explicit_branch: Optional[str] = None) -> str:
    if explicit_branch and explicit_branch.strip():
        return explicit_branch.strip()
    if has_explicit_main_override(message):
        return (_env("GITHUB_BRANCH", "main") or "main").strip()
    return create_orion_branch_name(path)


def execute_orion_single_file_fix(payload: OrionGitWriteIn) -> Dict[str, Any]:
    branch_name = (payload.branch or "").strip() or create_orion_branch_name(payload.path)
    base_branch = (payload.base_branch or _env("GITHUB_BRANCH", "main") or "main").strip()

    if branch_name != base_branch:
        git_create_branch(
            BranchCreateIn(
                branch_name=branch_name,
                source_branch=base_branch,
            )
        )

    commit_result = git_commit_file(
        CommitFileIn(
            path=payload.path,
            content=payload.content,
            message=payload.commit_message,
            branch=branch_name,
        )
    )

    pr_result: Dict[str, Any] = {"ok": False, "created": False}
    if payload.open_pr and branch_name != base_branch:
        try:
            pr_result = git_open_pr(
                PullRequestIn(
                    title=payload.commit_message[:200],
                    body=f"Governed Orion fix for `{payload.path}`.",
                    head=branch_name,
                    base=base_branch,
                )
            )
            pr_result["created"] = True
        except Exception as e:
            pr_result = {"ok": False, "created": False, "error": str(e)}

    return {
        "ok": True,
        "repo": _env("GITHUB_REPO"),
        "base_branch": base_branch,
        "branch": branch_name,
        "path": payload.path,
        "commit": commit_result,
        "pull_request": pr_result,
    }


def execute_orion_branch_create(*, branch_name: str, source_branch: Optional[str] = None) -> Dict[str, Any]:
    if not (branch_name or "").strip():
        raise HTTPException(status_code=400, detail="branch_name required")
    data = git_create_branch(
        BranchCreateIn(
            branch_name=branch_name.strip(),
            source_branch=(source_branch or _env("GITHUB_BRANCH", "main") or "main").strip(),
        )
    )
    return {
        "ok": True,
        "repo": _env("GITHUB_REPO"),
        "source_branch": data.get("source_branch"),
        "branch": data.get("new_branch"),
        "ref": data.get("ref"),
        "sha": data.get("sha"),
    }


@router.get("/health")
def orion_health():
    return {
        "ok": True,
        "service": "orion_internal",
        "github_bridge_ready": bool(_env("GITHUB_TOKEN")) and bool(_env("GITHUB_REPO")),
        "default_branch": _env("GITHUB_BRANCH", "main"),
    }


@router.post("/github/write")
def orion_github_write(payload: OrionGitWriteIn):
    return execute_orion_single_file_fix(payload)


@router.post("/github/branch")
def orion_github_branch(payload: OrionBranchCreateIn):
    return execute_orion_branch_create(
        branch_name=payload.branch_name,
        source_branch=payload.source_branch,
    )
