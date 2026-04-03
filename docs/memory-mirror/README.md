# Memory Mirror

This repo branch pair is the fallback mirror for the compacted memory state.

Branch contract:
- `main` = last validated fallback snapshot
- `update/memory-mirror-phase1` = working snapshot for the current compaction pass
- PR = reviewable diff between snapshots

Current durable snapshot kept in GitHub:

- `fatalacris/Hermes` workflow: `main` is stable baseline; `develop` is integration via PRs; mirror validated local setup to GitHub periodically.
- User prefers to close chat sessions and start fresh for concrete tasks, relying on persistent memory for continuity.
- User is on Windows with WSL; Windows Chrome is logged in, and the Telegram summary bot is already available.
- User prefers a dedicated workspace directory under `C:\Users\spex2\Hermes FATI` for files/projects created during this work.
- Decision order: shared task queue first, local session second; then relevant skills; then idea-log.json.
- FATI Mini Control path: `/mnt/c/Users/spex2/Hermes FATI/fati-mini-control`; plugin path: `/home/fati_hermes/.hermes/plugins/fati-mini-control`.
- Buckets: memory=facts; skills/docs=workflows; tasks=active; ideas=idea-log.json.
- Telegram/CLI error snippets may include broken ANSI color codes like `?[0m?[1;31m`; strip ANSI escapes before interpreting the real error text.
- For Hermes model/provider changes, update `model.provider` and `model.default` together, then verify with `hermes config`/`doctor`.

Use this branch setup as the rollback path if a future memory compaction removes something important.
