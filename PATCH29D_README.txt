PATCH29D — Orion GitHub Write Finalization

Files included:
- app/main.py
- app/routes/internal/orion_internal.py
- app/runtime/capability_registry.py

What changed:
- Added Orion support for explicit branch creation via chat.
- Added Orion support for file creation with literal content via chat.
- Kept governed approval flow for write operations.
- Extended capability registry for branch/file creation awareness.

Suggested tests after deploy:
1) @Orion crie uma branch chamada test-runtime-access
2) de acordo
3) @Orion crie `docs/test_runtime.txt` com conteúdo "runtime ok"
4) de acordo
5) Verify branch/PR/file on GitHub.
