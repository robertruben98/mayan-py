# Contributing to mayan-py

Thanks for your interest in improving `mayan-py`. This guide covers the local
setup and the quality bar every change must clear.

## Development setup

```bash
git clone https://github.com/robertruben98/mayan-py
cd mayan-py
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Python 3.9+ is supported. The package uses a `src/` layout (import name
`mayan`).

## Quality gates

All of these must pass before a PR is merged (CI enforces them on Python
3.9–3.13):

```bash
ruff check .            # lint + import sorting
mypy                    # strict type checking (targets 3.10)
pytest                  # unit tests (mocked HTTP, no network)
```

Run the live smoke test against the real keyless API only when needed:

```bash
pytest -m integration
```

## Conventions

- **Test-driven.** Add or update tests for any behavior change; write the
  failing test first, then the implementation.
- **No live network in unit tests.** Mock HTTP with `respx` (see `tests/`).
- **Type everything.** `mypy --strict` must stay clean; the package ships
  `py.typed`.
- **Annotations stay 3.9-safe.** Runtime-evaluated annotations (pydantic
  fields, signatures) use `typing.Optional`/`Union`, not PEP 604 `X | None`,
  because pydantic resolves them at runtime. Ruff's `UP007`/`UP045` are
  disabled for this reason.
- **Multi-ecosystem.** Addresses and raw amounts are kept as strings so Solana,
  EVM and Sui values round-trip without precision loss.
- **Docstrings.** Public classes and methods use Google-style docstrings with
  `Args`/`Returns`/`Raises`; response model fields use `Field(description=...)`.

## Submitting changes

1. Branch off `main` (e.g. `feat/...`, `fix/...`, `docs/...`).
2. Make the change with tests and docs.
3. Ensure ruff + mypy + pytest are green locally.
4. Update `CHANGELOG.md` under an `Unreleased`/next-version heading.
5. Open a PR against `main`; describe the change and how you verified it.

## Releasing

Maintainers: bump the version in `pyproject.toml` and `src/mayan/__init__.py`,
update `CHANGELOG.md`, then build and publish:

```bash
uv build
uvx twine check dist/*
uvx twine upload dist/*
```
