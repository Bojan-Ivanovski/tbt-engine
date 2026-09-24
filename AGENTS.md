# Working Agreement

This repository is a standalone Python backtesting engine. Keep changes focused on the engine and avoid assumptions that belong to Trader Lens or any other consuming application.

## How We Work

1. Read the relevant GitHub ticket and inspect the current repository before proposing or making changes.
2. Translate the ticket into a concrete implementation plan and identify any ambiguity or meaningful design choice.
3. Discuss decisions that depart from the ticket before implementing them. Once agreed, treat those decisions as part of the requirements.
4. Preserve existing behavior during refactors unless the ticket explicitly requests a behavior change.
5. Implement the complete in-scope change, update documentation, and verify it before handing it off.
6. Do not commit, push, close tickets, or make other external changes unless explicitly requested.

## Repository Conventions

- `tbt_engine/` is the root-level import package. Do not introduce a `src/` directory or restore the old `engine` package without an explicit decision to change the layout.
- Keep implementation out of package `__init__.py` files. Use them only for documentation and explicit public exports through `__all__`.
- Organize reusable behavior by domain, such as `providers`, `signals`, and `strategies`.
- Examples belong in `examples/` and should configure and consume reusable library code. Do not define substantial strategy implementations inside example runners.
- Keep the package standalone. Application-specific orchestration, persistence, API contracts, and UI assumptions belong in their respective consumers.
- Use `tbt_engine` logger namespaces, normally through `logging.getLogger(__name__)`.
- Maintain complete type annotations compatible with strict Pyright.
- Include public typed modules in the distributed package and preserve the `py.typed` marker.

## Development Workflow

The checked-in `.python-version` selects the project Python through pyenv. Use a local virtual environment for dependencies:

```bash
pyenv install --skip-existing 3.14.6
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Before considering a change complete, run:

```bash
isort --check-only .
black --check .
pyright
```

For packaging or repository-structure changes, also run:

```bash
python -m build
```

Confirm that both the wheel and source distribution build, that the wheel imports outside the repository root, and that runnable examples still import and execute correctly. Remove generated build artifacts after verification; do not commit caches, local environments, egg metadata, `build/`, or `dist/`.

## Testing Expectations

- Prefer deterministic providers and fixed in-memory market data for engine tests and smoke checks.
- Do not depend on live Yahoo Finance responses to verify core behavior.
- Test public imports when changing exports or packaging.
- For behavior-preserving refactors, exercise representative trades and compare observable results such as accepted trades, ending equity, and return percentage.

## Commit Conventions

Only create a commit when requested. For issue work, use this subject format:

```text
<Type>[#<ticket number>]: <short description>
```

Example:

```text
Refactor[#2]: standardize the Python package layout
```

Use a commit body that summarizes the implementation and records decisions, especially departures from the ticket:

```text
Summery of changes:
 - ...
 - ...

Desisions made durring the changes:
 - ...
 - Explain any decision outside what the ticket listed.
```

Keep the subject concise, write body bullets as completed actions, and reference the ticket number in the subject.
