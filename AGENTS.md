# Repository Guidelines

## Project Structure & Module Organization
- Current repo contains docs (`READ.md`, `siyou.md`). Place new code under `src/faers_signal/`; tests under `tests/`; scripts under `scripts/`; docs under `docs/`; assets under `assets/`.
- Package name: `faers_signal` (snake_case). Example: `src/faers_signal/metrics.py` with a matching test `tests/test_metrics.py`.

## Build, Test, and Development Commands
- Create venv (PowerShell): `python -m venv .venv; .\.venv\Scripts\Activate.ps1`
- Install deps (when present): `pip install -e .[dev]` or `pip install -r requirements.txt`
- Run tests: `pytest -q`
- Lint/format (if configured): `ruff check .` and `black .`

## Coding Style & Naming Conventions
- Language: Python (3.11+ recommended).
- Style: PEP 8. Use Black for formatting and Ruff for linting.
- Naming: modules/files `snake_case.py`; classes `PascalCase`; functions/vars `snake_case`; constants `UPPER_CASE`.
- Docstrings: concise Google‑style with examples where useful.

## Testing Guidelines
- Framework: `pytest`. Name tests `test_*.py` and mirror module structure.
- Fixtures live in `tests/conftest.py`. Prefer small, deterministic unit tests; add integration tests as needed.
- Coverage: aim for 80%+ once CI is added. Example: `pytest --cov=faers_mini_signal -q` (requires coverage plugins).

## Commit & Pull Request Guidelines
- Commit small and often; keep each commit focused and revertable. Write clean, descriptive messages in imperative mood. (GitHubには細かくコミットし、コミットメッセージは綺麗に書くこと)
- Commits: follow Conventional Commits, e.g., `feat: add signal scoring` or `fix: handle empty input`.
- PRs: include summary, rationale, linked issues (`#123`), tests for new/changed behavior, and notes on data or schema impacts.
- Ensure tests, lint, and format pass locally before requesting review.

## Security & Configuration Tips
- Never commit secrets or raw PHI/PII. Use `.env` (git‑ignored) and provide `.env.example` when needed.
- Store large data in `data/` and add an appropriate `.gitignore` entry.

### Git Identity (このリポジトリの推奨ローカル設定)
- メインメンテナの署名情報（ローカル設定の例）:
  - `git config user.name "mirune0014"`
  - `git config user.email "eem2503@ed.socu.ac.jp"`
- 他のコントリビュータは自分の GitHub に登録済みのメール/名前を設定してください。
- 既存コミットの著者を修正する場合は `git rebase -i` や `git filter-branch` を利用。

## Agent‑Specific Notes
- Add new modules under `src/faers_signal/`; avoid placing code at the repo root.
- Keep changes minimal and focused; update this file if conventions evolve.
