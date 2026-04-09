from __future__ import annotations

import base64
import logging
import os
import requests
from typing import Dict, Any, List

from app.self_heal.code_emitter import code_emitter

logger = logging.getLogger(__name__)


class GitHubPRWriterEngine:
    """
    Level 3:
    Converts PR payload into real commits on GitHub
    via GitHub Contents API.
    """

    def __init__(self):
        self.enabled = os.getenv(
            "AUTO_PR_WRITE_ENABLED",
            "true",
        ).lower() in ("1", "true", "yes", "on")

        self.github_token = os.getenv("GITHUB_TOKEN")
        self.backend_repo = os.getenv("GITHUB_REPO")
        self.frontend_repo = os.getenv("GITHUB_REPO_WEB")
        self.branch = os.getenv("GITHUB_BRANCH", "main")

    def execute(self, capability_name: str):

        if not self.enabled:
            return

        payload = code_emitter.generated_artifacts.get(
            capability_name
        )

        if not payload:
            logger.warning(
                "PR_WRITER_NO_PAYLOAD %s",
                capability_name,
            )
            return

        pr_payload = payload.get("pr_payload")

        if not pr_payload:
            logger.warning(
                "PR_WRITER_NO_PR_DATA %s",
                capability_name,
            )
            return

        logger.warning(
            "PR_WRITER_EXECUTION_READY %s",
            capability_name,
        )

        if pr_payload["backend_enabled"]:
            self._write_files(
                repo=self.backend_repo,
                files=pr_payload["backend_files"],
                capability_name=capability_name,
            )

        if pr_payload["frontend_enabled"]:
            self._write_files(
                repo=self.frontend_repo,
                files=pr_payload["frontend_files"],
                capability_name=capability_name,
            )

    def _write_files(
        self,
        repo: str,
        files: List[Dict[str, Any]],
        capability_name: str,
    ):

        if not repo:
            return

        for file in files:

            path = file["path"]
            content = file["content"]

            encoded = base64.b64encode(
                content.encode("utf-8")
            ).decode("utf-8")

            url = f"https://api.github.com/repos/{repo}/contents/{path}"

            response = requests.put(
                url,
                headers={
                    "Authorization": f"Bearer {self.github_token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "message": f"auto: orkio generated {capability_name}",
                    "content": encoded,
                    "branch": self.branch,
                },
                timeout=15,
            )

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


pr_writer = GitHubPRWriterEngine()
