from __future__ import annotations

import logging
import os
import requests

from app.self_heal.code_emitter import code_emitter


logger = logging.getLogger(__name__)


class GitHubBridgeExecutor:

    def __init__(self):
        self.enabled = os.getenv(
            "AUTO_PR_EXECUTION_ENABLED",
            "true",
        ).lower() in ("1", "true", "yes")

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
                "GITHUB_BRIDGE_NO_PAYLOAD %s",
                capability_name,
            )
            return

        pr_payload = payload.get("pr_payload")

        if not pr_payload:
            logger.warning(
                "GITHUB_BRIDGE_NO_PR_DATA %s",
                capability_name,
            )
            return

        logger.warning(
            "GITHUB_BRIDGE_EXECUTION_READY %s",
            capability_name,
        )

        if pr_payload["backend_enabled"]:
            self._send_files(
                self.backend_repo,
                pr_payload["backend_files"],
                capability_name,
            )

        if pr_payload["frontend_enabled"]:
            self._send_files(
                self.frontend_repo,
                pr_payload["frontend_files"],
                capability_name,
            )

    def _send_files(
        self,
        repo: str,
        files: list,
        capability_name: str,
    ):

        if not repo:
            return

        for file in files:

            path = file["path"]

            logger.warning(
                "GITHUB_BRIDGE_FILE_READY repo=%s path=%s capability=%s",
                repo,
                path,
                capability_name,
            )
