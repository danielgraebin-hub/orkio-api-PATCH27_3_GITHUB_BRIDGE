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


# =========================================================
# ENV helpers
# =========================================================

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip().strip('"').strip("'")


# =========================================================
# MODELS
# =========================================================

class OrionGitWriteIn(BaseModel):
    path: str
    content: str
    commit_message: str
    branch: Optional[str] = None
    base_branch: Optional[str] = None
    open_pr: bool = True


class OrionBranchCreateIn(BaseModel):
    branch_name: str
    source_branch: Optional[str] = None


# =========================================================
# HELPERS
# =========================================================

def create_orion_branch_name(path: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9/_\-.]+", "-", path.lower())
    cleaned = cleaned.replace("/", "-").replace("_", "-").replace(".", "-")
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")[:48]

    return f"orion-fix/{cleaned}-{int(time.time())}"


# =========================================================
# EXECUTION LAYER
# =========================================================

def execute_orion_branch_create(
    *,
    branch_name: str,
    source_branch: Optional[str] = None,
):

    if not branch_name.strip():
        raise HTTPException(400, "branch_name required")

    data = git_create_branch(
        BranchCreateIn(
            branch_name=branch_name.strip(),
            source_branch=(
                source_branch
                or _env("GITHUB_BRANCH", "main")
            ),
        )
    )

    return {
        "ok": True,
        "repo": _env("GITHUB_REPO"),
        "branch": data["new_branch"],
        "ref": data["ref"],
        "sha": data["sha"],
    }


def execute_orion_single_file_fix(
    payload: OrionGitWriteIn
):

    branch_name = (
        payload.branch
        or create_orion_branch_name(payload.path)
    )

    base_branch = (
        payload.base_branch
        or _env("GITHUB_BRANCH", "main")
    )

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

    pr_result = {"created": False}

    if payload.open_pr:

        try:

            pr_result = git_open_pr(
                PullRequestIn(
                    title=payload.commit_message,
                    body=f"Governed Orion patch for `{payload.path}`",
                    head=branch_name,
                    base=base_branch,
                )
            )

            pr_result["created"] = True

        except Exception as e:

            pr_result = {
                "created": False,
                "error": str(e),
            }

    return {

        "ok": True,
        "repo": _env("GITHUB_REPO"),

        "branch": branch_name,
        "base_branch": base_branch,

        "path": payload.path,

        "commit": commit_result,
        "pull_request": pr_result,
    }


# =========================================================
# ROUTES
# =========================================================

@router.get("/health")
def orion_health():

    return {

        "ok": True,

        "service": "orion_internal",

        "github_bridge_ready":
            bool(_env("GITHUB_TOKEN"))
            and bool(_env("GITHUB_REPO")),

        "default_branch":
            _env("GITHUB_BRANCH", "main"),
    }


# =========================================================
# CREATE BRANCH (RUNTIME CHAT SUPPORT)
# =========================================================

@router.post("/github/branch")
def orion_create_branch(payload: OrionBranchCreateIn):

    return execute_orion_branch_create(

        branch_name=payload.branch_name,

        source_branch=payload.source_branch,
    )


# =========================================================
# WRITE FILE (RUNTIME CHAT SUPPORT)
# =========================================================

@router.post("/github/write")
def orion_write_file(payload: OrionGitWriteIn):

    return execute_orion_single_file_fix(payload)


# =========================================================
# READ OPERATIONS
# =========================================================

@router.get("/github/tree")
def orion_repo_tree(branch: Optional[str] = None):

    return git_tree(branch=branch)


@router.get("/github/file")
def orion_repo_file(
    path: str,
    branch: Optional[str] = None,
):

    return git_file(path=path, branch=branch)


@router.get("/github/search")
def orion_repo_search(
    query: str,
    branch: Optional[str] = None,
):

    return git_search(query=query, branch=branch)


@router.get("/github/health")
def orion_repo_health():

    return git_health()
