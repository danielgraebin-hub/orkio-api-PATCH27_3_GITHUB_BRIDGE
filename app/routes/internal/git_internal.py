from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/internal/git", tags=["git-internal"])

def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name, "true" if default else "false") or "").strip().strip('"').strip("\'").lower()
    return raw in ("1", "true", "yes", "on")

def _write_enabled() -> bool:
    return _bool_env("GITHUB_AUTOMATION_ALLOWED", False) and _bool_env("AUTO_CODE_EMISSION_ENABLED", False)

def _pr_enabled() -> bool:
    return _bool_env("GITHUB_PR_RUNTIME_ENABLED", False) and (_bool_env("AUTO_PR_BACKEND_ENABLED", False) or _bool_env("AUTO_PR_FRONTEND_ENABLED", False) or _bool_env("AUTO_PR_WRITE_ENABLED", False))

def _safe_main_write_allowed() -> bool:
    return _bool_env("ALLOW_GITHUB_MAIN_DIRECT", False)

def _ensure_write_enabled() -> None:
    if not _write_enabled():
        raise HTTPException(status_code=403, detail="GitHub write runtime disabled by environment")

def _guard_branch_write(branch: str) -> None:
    resolved = (branch or "").strip()
    default_branch = _env("GITHUB_BRANCH", "main")
    if resolved == default_branch and not _safe_main_write_allowed():
        raise HTTPException(status_code=403, detail=f"Direct write on '{default_branch}' blocked by safe evolution policy")


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip().strip('"').strip("'")


def _repo() -> str:
    repo = _env("GITHUB_REPO")
    if not repo:
        raise HTTPException(status_code=500, detail="GITHUB_REPO not configured")
    return repo


def _token() -> str:
    token = _env("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not configured")
    return token


def _branch(branch: Optional[str]) -> str:
    return (branch or _env("GITHUB_BRANCH", "main") or "main").strip()


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "orkio-github-bridge/1.0",
    }


def _api_base() -> str:
    return _env("GITHUB_API_BASE", "https://api.github.com").rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{_api_base()}{path}"
    try:
        resp = requests.request(
            method,
            url,
            headers=_headers(),
            params=params,
            json=json_body,
            timeout=30,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"github request failed: {e}")

    if resp.status_code >= 400:
        detail: Any
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise HTTPException(
            status_code=resp.status_code,
            detail={"github_error": detail, "path": path},
        )

    if resp.status_code == 204:
        return {}

    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def _get_ref_sha(branch: str) -> str:
    data = _request("GET", f"/repos/{_repo()}/git/ref/heads/{branch}")
    return data["object"]["sha"]


def _get_file(path: str, branch: str) -> Dict[str, Any]:
    return _request(
        "GET",
        f"/repos/{_repo()}/contents/{path}",
        params={"ref": branch},
    )


class BranchCreateIn(BaseModel):
    branch_name: str = Field(min_length=3, max_length=120)
    source_branch: Optional[str] = Field(default=None, max_length=120)


class CommitFileIn(BaseModel):
    path: str = Field(min_length=1)
    content: str = Field(min_length=0)
    message: str = Field(min_length=3, max_length=300)
    branch: Optional[str] = Field(default=None, max_length=120)


class PullRequestIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(default="", max_length=20000)
    head: str = Field(min_length=1, max_length=120)
    base: Optional[str] = Field(default=None, max_length=120)


@router.get("/health")
def git_health():
    return {
        "ok": True,
        "service": "git_internal",
        "repo": _env("GITHUB_REPO"),
        "default_branch": _env("GITHUB_BRANCH", "main"),
        "token_configured": bool(_env("GITHUB_TOKEN")),
    }


@router.get("/tree")
def git_tree(branch: Optional[str] = Query(default=None)):
    branch_name = _branch(branch)
    commit_sha = _get_ref_sha(branch_name)
    data = _request(
        "GET",
        f"/repos/{_repo()}/git/trees/{commit_sha}",
        params={"recursive": "1"},
    )
    return {
        "repo": _repo(),
        "branch": branch_name,
        "tree": data.get("tree", []),
        "truncated": data.get("truncated", False),
    }


@router.get("/file")
def git_file(path: str = Query(...), branch: Optional[str] = Query(default=None)):
    branch_name = _branch(branch)
    data = _get_file(path, branch_name)

    content_b64 = data.get("content", "")
    encoding = data.get("encoding", "")

    decoded = ""
    if encoding == "base64" and content_b64:
        decoded = base64.b64decode(content_b64).decode("utf-8", errors="replace")

    return {
        "repo": _repo(),
        "branch": branch_name,
        "path": path,
        "sha": data.get("sha"),
        "size": data.get("size"),
        "content": decoded,
    }


@router.get("/search")
def git_search(
    query: str = Query(..., min_length=2),
    branch: Optional[str] = Query(default=None),
):
    branch_name = _branch(branch)
    q = f"repo:{_repo()} {query}"
    data = _request("GET", "/search/code", params={"q": q, "per_page": 50})
    items = data.get("items", [])
    return {
        "repo": _repo(),
        "branch": branch_name,
        "query": query,
        "count": len(items),
        "items": [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "sha": item.get("sha"),
                "url": item.get("html_url"),
            }
            for item in items
        ],
    }


@router.post("/branch")
def git_create_branch(payload: BranchCreateIn):
    _ensure_write_enabled()
    source_branch = _branch(payload.source_branch)
    base_sha = _get_ref_sha(source_branch)
    ref = f"refs/heads/{payload.branch_name}"

    data = _request(
        "POST",
        f"/repos/{_repo()}/git/refs",
        json_body={
            "ref": ref,
            "sha": base_sha,
        },
    )

    return {
        "ok": True,
        "source_branch": source_branch,
        "new_branch": payload.branch_name,
        "ref": data.get("ref"),
        "sha": data.get("object", {}).get("sha"),
    }


@router.post("/commit")
def git_commit_file(payload: CommitFileIn):
    _ensure_write_enabled()
    branch_name = _branch(payload.branch)
    _guard_branch_write(branch_name)

    existing_sha = None
    file_preexisted = False

    try:
        existing = _get_file(payload.path, branch_name)
        existing_sha = existing.get("sha")
        file_preexisted = True
    except HTTPException as e:
        if e.status_code == 404:
            existing_sha = None
            file_preexisted = False
        else:
            raise

    encoded = base64.b64encode(payload.content.encode("utf-8")).decode("utf-8")

    body: Dict[str, Any] = {
        "message": payload.message,
        "content": encoded,
        "branch": branch_name,
    }
    if existing_sha:
        body["sha"] = existing_sha

    data = _request(
        "PUT",
        f"/repos/{_repo()}/contents/{payload.path}",
        json_body=body,
    )

    commit = data.get("commit", {}) or {}
    content = data.get("content", {}) or {}

    return {
        "ok": True,
        "repo": _repo(),
        "branch": branch_name,
        "path": payload.path,
        "created": not file_preexisted,
        "updated": file_preexisted,
        "content_sha": content.get("sha"),
        "commit_sha": commit.get("sha"),
        "commit_url": commit.get("html_url"),
    }


@router.post("/pr")
def git_open_pr(payload: PullRequestIn):
    if not _pr_enabled():
        raise HTTPException(status_code=403, detail="GitHub PR runtime disabled by environment")
    base_branch = _branch(payload.base)
    data = _request(
        "POST",
        f"/repos/{_repo()}/pulls",
        json_body={
            "title": payload.title,
            "body": payload.body,
            "head": payload.head,
            "base": base_branch,
        },
    )
    return {
        "ok": True,
        "number": data.get("number"),
        "state": data.get("state"),
        "url": data.get("html_url"),
    }


@router.get("/capabilities")
def git_capabilities():
    return {
        "ok": True,
        "service": "git_internal",
        "repo": _env("GITHUB_REPO"),
        "default_branch": _env("GITHUB_BRANCH", "main"),
        "token_configured": bool(_env("GITHUB_TOKEN")),
        "write_enabled": _write_enabled(),
        "pr_enabled": _pr_enabled(),
        "main_direct_write_allowed": _safe_main_write_allowed(),
    }
