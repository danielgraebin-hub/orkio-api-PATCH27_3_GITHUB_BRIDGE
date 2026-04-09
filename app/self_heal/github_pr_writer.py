from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from app.self_heal.code_emitter import code_emitter

logger = logging.getLogger(__name__)


class GitHubPRWriterEngine:
    """
    Smart commit engine:
    - creates files when they do not exist
    - updates files when they already exist (SHA-aware)
    - logs commit success/failure per file
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("AUTO_PR_WRITE_ENABLED", "true").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self.github_token = (os.getenv("GITHUB_TOKEN") or "").strip()
        self.backend_repo = (os.getenv("GITHUB_REPO") or "").strip()
        self.frontend_repo = (os.getenv("GITHUB_REPO_WEB") or "").strip()
        self.branch = (os.getenv("GITHUB_BRANCH") or "main").strip()

    def execute(self, capability_name: str) -> None:
        if not self.enabled:
            return

        payload = code_emitter.generated_artifacts.get(capability_name)
        if not payload:
            logger.warning("PR_WRITER_NO_PAYLOAD %s", capability_name)
            return

        pr_payload = payload.get("pr_payload")
        if not pr_payload:
            logger.warning("PR_WRITER_NO_PR_DATA %s", capability_name)
            return

        logger.warning("PR_WRITER_EXECUTION_READY %s", capability_name)

        if pr_payload.get("backend_enabled"):
            self._write_files(
                repo=self.backend_repo,
                files=pr_payload.get("backend_files", []),
                capability_name=capability_name,
            )

        if pr_payload.get("frontend_enabled"):
            self._write_files(
                repo=self.frontend_repo,
                files=pr_payload.get("frontend_files", []),
                capability_name=capability_name,
            )

    def _write_files(
        self,
        repo: str,
        files: List[Dict[str, Any]],
        capability_name: str,
    ) -> None:
        if not repo:
            logger.warning("PR_WRITER_REPO_MISSING %s", capability_name)
            return

        if not self.github_token:
            logger.warning("PR_WRITER_TOKEN_MISSING %s", capability_name)
            return

        for file in files:
            try:
                path = str(file["path"])
                content = str(file["content"])

                sha = self._get_file_sha(repo=repo, path=path)

                response = self._put_file(
                    repo=repo,
                    path=path,
                    content=content,
                    capability_name=capability_name,
                    sha=sha,
                )

                if response is None:
                    logger.warning(
                        "PR_WRITER_COMMIT_FAILED repo=%s path=%s status=unknown",
                        repo,
                        path,
                    )
                    continue

                if response.status_code in (200, 201):
                    logger.warning(
                        "PR_WRITER_FILE_COMMITTED repo=%s path=%s",
                        repo,
                        path,
                    )
                else:
                    logger.warning(
                        "PR_WRITER_COMMIT_FAILED repo=%s path=%s status=%s",
                        repo,
                        path,
                        response.status_code,
                    )
            except Exception:
                logger.exception(
                    "PR_WRITER_FILE_EXCEPTION repo=%s capability=%s",
                    repo,
                    capability_name,
                )

    def _get_file_sha(self, repo: str, path: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params={"ref": self.branch},
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                sha = data.get("sha")
                return str(sha) if sha else None

            if response.status_code == 404:
                return None

            logger.warning(
                "PR_WRITER_SHA_FETCH_FAILED repo=%s path=%s status=%s",
                repo,
                path,
                response.status_code,
            )
            return None
        except Exception:
            logger.exception("PR_WRITER_SHA_FETCH_EXCEPTION repo=%s path=%s", repo, path)
            return None

    def _put_file(
        self,
        repo: str,
        path: str,
        content: str,
        capability_name: str,
        sha: Optional[str],
    ) -> Optional[requests.Response]:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        body: Dict[str, Any] = {
            "message": f"auto: orkio generated {capability_name}",
            "content": encoded,
            "branch": self.branch,
        }
        if sha:
            body["sha"] = sha

        try:
            return requests.put(
                url,
                headers=self._headers(),
                json=body,
                timeout=20,
            )
        except Exception:
            logger.exception("PR_WRITER_PUT_EXCEPTION repo=%s path=%s", repo, path)
            return None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
        }


pr_writer = GitHubPRWriterEngine()
