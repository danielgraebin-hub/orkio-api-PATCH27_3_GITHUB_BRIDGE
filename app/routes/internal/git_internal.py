
"""
git_internal.py — Orkio GitHub Bridge (WRITE‑ENABLED VERSION)
PATCH 29D — Runtime GitHub write support with safe create/update behavior.
"""

import os
import base64
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/internal/git", tags=["internal-git"])

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
DEFAULT_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()

if not GITHUB_TOKEN:
    print("WARNING: GITHUB_TOKEN not configured")

GITHUB_API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }


def _repo_parts(repo: str):
    if "/" not in repo:
        raise ValueError("Repo must be owner/repo format")
    owner, name = repo.split("/", 1)
    return owner, name


def github_get_file(repo: str, path: str, branch: str = DEFAULT_BRANCH):
    owner, name = _repo_parts(repo)

    url = f"{GITHUB_API}/repos/{owner}/{name}/contents/{path}?ref={branch}"

    r = requests.get(url, headers=_headers())

    if r.status_code == 404:
        return None

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()


def github_create_or_update_file(
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str = DEFAULT_BRANCH,
):
    """
    Create file if not exists.
    Update file if exists.
    """

    owner, name = _repo_parts(repo)

    existing = github_get_file(repo, path, branch)

    encoded = base64.b64encode(content.encode()).decode()

    payload = {
        "message": message,
        "content": encoded,
        "branch": branch,
    }

    if existing:
        payload["sha"] = existing["sha"]

    url = f"{GITHUB_API}/repos/{owner}/{name}/contents/{path}"

    r = requests.put(url, headers=_headers(), json=payload)

    if r.status_code not in (200, 201):
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()


@router.post("/write-file")
def write_file(repo: str, path: str, content: str, message: str):
    """
    Orion runtime entrypoint.
    Creates or updates file safely.
    """

    if not GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="Missing GITHUB_TOKEN")

    return github_create_or_update_file(
        repo=repo,
        path=path,
        content=content,
        message=message,
    )
