PATCH29C — Orion GitHub Governed Access

Included files:
- app/main.py
- app/routes/internal/orion_internal.py
- app/runtime/capability_registry.py

What this patch enables:
1. Orion can verify real GitHub access through the existing bridge.
2. Orion can read repo health, tree, search results and file contents from GitHub.
3. Orion can prepare and execute a governed single-file fix on GitHub when:
   - the request targets Orion
   - the message is a GitHub/code/repo intent
   - the message includes a file path
   - the founder/admin approval is explicit in-context ("de acordo", "autorizado", "aprovado", "pode seguir")
4. Execution writes to a new branch and opens a PR automatically.
5. Read operations do not require approval. Write operations do.

Important limitation:
- This patch is intentionally conservative. Governed write execution is single-file per request.
- It does not auto-deploy production.
- It does not auto-merge PRs.

Recommended env sanity:
- GITHUB_TOKEN set
- GITHUB_REPO set
- GITHUB_BRANCH set
- AUTO_PR_WRITE_ENABLED remains false if you do not want the self-heal pipeline to write automatically.
  This patch does not depend on AUTO_PR_WRITE_ENABLED; it uses the explicit GitHub bridge with founder approval.

Suggested tests:
1. @Orion verifique se temos acesso real ao GitHub agora.
2. @Orion liste a árvore do repo.
3. @Orion analise `app/main.py` no GitHub.
4. @Orion corrija `app/main.py` para [descrever ajuste]. (sem aprovação => analysis only)
5. @Orion de acordo, pode corrigir `app/main.py` para [descrever ajuste]. (with approval => branch + commit + PR)
