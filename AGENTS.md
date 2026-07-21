# Repository Instructions

## Python / uv

- This project is managed by `uv`, but commands should usually be run through
  `just` so the workspace-local uv cache is used.
- Prefer:
  - `just check`
  - `just smoke`
  - `just binary`
  - `just setup`
- If a direct `uv` command is necessary, prefix it with a workspace-local cache:

```bash
UV_CACHE_DIR=.uv-cache uv run --no-sync ruff check mediarchiver
```

Avoid using uv's default user cache during automated checks because Codex
sandboxing may block access to `~/.cache/uv`.
