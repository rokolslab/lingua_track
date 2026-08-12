# Repository Guidelines

## Project Structure & Module Organization

LinguaTrack is a Django 5 application. Project configuration, URL routing, and Celery setup live in `lingua_track/`. Feature code is split into Django apps: `users/` handles accounts and Telegram linking, `cards/` owns vocabulary cards, SM-2 scheduling, speech synthesis, and background tasks, while `bot_api/` exposes endpoints used by the bot. The standalone aiogram client is in `t_bot/`. Shared HTML is under `templates/`, reference material and CSV samples are in `docs/`, and deployment assets are in `deploy/`. The active pytest suite is in `tests/`.

## Build, Test, and Development Commands

Create a virtual environment, then install dependencies with:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run `python manage.py migrate` to update the local SQLite schema and `python manage.py runserver` to start Django. Use `python manage.py check` for a quick configuration check. Run `pytest` for the full suite; `pytest tests/test_sm2.py` targets scheduling logic, and `python run_tests.py --models` uses the repository's test wrapper. Pytest generates terminal and HTML coverage reports and enforces 80% overall coverage. Production services are defined in `deploy/docker-compose.yml`.

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation. Use `snake_case` for functions, variables, modules, and test methods; use `PascalCase` for models, forms, and test classes. Keep Django responsibilities in their conventional files (`models.py`, `views.py`, `forms.py`, `urls.py`) and create migrations through `python manage.py makemigrations`. No formatter or linter is currently configured, so keep imports grouped and changes consistent with nearby code.

## Testing Guidelines

Tests use pytest, pytest-django, fixtures from `tests/conftest.py`, and markers declared in `pytest.ini` (for example, `sm2`, `models`, `integration`, and `slow`). Name files `test_*.py`, classes `Test*`, and methods `test_*`. Mark database tests with `@pytest.mark.django_db` and add focused regression tests for bug fixes.

`pytest.ini` currently sets `--cov-fail-under=80`. Treat this as the existing project configuration, but measure and record the actual baseline before modernization work. An existing coverage-gate failure is not a new regression. Every change must at least avoid reducing the actual coverage of the affected code. Do not lower or remove the 80% threshold without a separate, explicit decision.

## Modernization Guidelines

Modernize incrementally; do not rewrite the project from scratch. Keep Django as the primary backend. Do not introduce React, FastAPI, microservices, or similarly large architectural changes without demonstrated need and a separate decision. First establish a stable, reproducible baseline, then update dependencies and develop functionality.

Separate technical-debt fixes from new features. Make minimal, logically related changes, avoid opportunistic fixes to unrelated problems, and preserve public application behavior unless a change is necessary. Maintain compatibility with existing data and migrations. Never rewrite existing migration files; create a new migration only for a real model change.

Update dependencies in controlled, small groups and run tests after each group. Keep Django on the 5.2 LTS line and apply updates within that line unless a separate task explicitly requires otherwise.

## Verification Rules

Before changing code, capture the baseline state of the relevant project area. Afterward, run the smallest sufficient verification set:

- `python manage.py check`;
- targeted pytest tests for the changed behavior;
- the full `pytest` suite afterward, when the environment permits;
- Docker/Compose configuration validation for deployment changes.

If a check already failed before the change, report it explicitly as a pre-existing failure and verify that the result did not worsen. Do not alter tests merely to obtain a green run when they expose a real application defect.

## Working Agreement

Do not run `git commit`, `git push`, merge branches, or create a pull request without a separate user command. Before a substantial change, briefly describe the intended modification. Afterward, report changed files and verification results. If an unexpected problem would materially expand task scope, stop at analysis and describe it instead of performing a large incidental refactor.

## Commit & Pull Request Guidelines

Recent history uses short, descriptive Russian commit summaries rather than Conventional Commits. Keep each commit focused and write an imperative summary that states the outcome. Pull requests should explain the change, list validation commands, link relevant issues, call out migrations or configuration changes, and include screenshots for template/UI updates.

## Security & Configuration

Never commit `.env` files, API keys, bot tokens, generated audio, or local databases. Do not assume existing configuration values are safe merely because they are already tracked in the repository. Base production configuration on `deploy/env.production.example`; production secrets must come only from environment variables or deployment tooling. Never expose real secrets in logs, reports, or documentation.
