# Contributing to the ConfigurationDesk MCP Server

Thanks for helping improve the ConfigurationDesk MCP Server. This guide covers how to set up a development environment, the conventions we follow, and how to get a change merged.

- **New to the codebase?** Read the [Architecture overview](ARCHITECTURE.md).
- **Adding a tool or domain?** Follow the Extending guide.
- **Configuring the server?** See the Configuration reference.

---

## 1. Repository shape

Two independently usable Python packages live in one repository:

| Package | Path | Role |
| --- | --- | --- |
| `configurationdesk-com-bridge` | `configurationdesk_com_bridge/` | Open-source COM automation library (the SDK surface). |
| `configurationdesk-mcp-server` | `ConfigurationDeskMCP/` | The FastMCP server: tools, services, resources, prompts. |

The server **depends on** the bridge. The bridge **must not** import from the server. See [AGENTS.md](AGENTS.md) for the non-obvious constraints that reviewers enforce.

---

## 2. Development environment

Prerequisites: **Windows 10/11**, [**uv**](https://docs.astral.sh/uv/), and — for running tools against the real application — **dSPACE ConfigurationDesk 2026-A or later**. uv installs and manages the Python interpreter (3.11+) for you.

Install uv if you do not already have it:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# or: winget install astral-sh.uv
```

### Install development dependencies

```powershell
uv sync --all-packages
```

This creates an isolated `.venv` and installs both workspace members in editable mode with the shared development tooling. This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): The root [pyproject.toml](pyproject.toml) ties the two member packages together, shares a single `uv.lock`, and resolves dependencies from public PyPI.

For regular MCP client use, no separate setup command is required: `ConfigurationDeskMCP.cmd` creates or updates the environment on its first run.

---

## 3. Coding standards

The essentials:

- **Layering is sacred.** Tool → Service → COM bridge → COM. Never call COM from a tool or service; always use `await dispatch(...)`. Never import `sources` from `configurationdesk_com_bridge`.

- **Type hints** on every public function; start each module with `from __future__ import annotations`.

- **Tool naming:** `snake_case` verbs (`create_project`, `list_models`). The service and COM functions share the tool's base name.

- **Formatting & linting with Ruff** (config: `ruff.toml`, line length 100, Black-compatible):

  ```powershell
  uv run ruff check .
  uv run ruff format .
  ```

- When dependencies are unavailable, gate syntax offline:

  ```powershell
  py -3.11 -m py_compile <file>
  ```

---

## 4. Testing

Tests live in `ConfigurationDeskMCP/tests/`. The retained suite is deterministic and needs no ConfigurationDesk installation.

```powershell
uv run pytest ConfigurationDeskMCP/tests
```

Every new or changed tool should be covered by at least a **contract test** (registration, name, description, annotations, input schema) so the change is validated without hardware. Refer to the Extending guide for the test-file map.

---

## 5. Local quality gate (run before every PR)

Reproduce the CI checks locally - they must all pass:

```powershell
uv run ruff check .                                  # lint (matches CI)
uv run ruff format --check .                          # formatting
uv run pytest ConfigurationDeskMCP/tests              # unit + contract tests
uv run configurationdesk-mcp --list-tools             # sanity: tools register
```

Pre-PR checklist (also in the `branch-validation-checklist` skill):

- [ ] Ruff lint and format are clean.

- [ ] Deterministic tests pass on Python 3.11.

- [ ] New tools have honest annotations and a description that states prerequisites.

- [ ] Domain facts in COM wrappers cite a dSPACE source (see [§7](#7-domain-knowledge)).

- [ ] Docs updated: domain tables in [README](README.md) and docs/tools/README.md; a tool-spec page if warranted.

- [ ] No `sources` import leaked into `configurationdesk_com_bridge`.

---

## 6. Continuous integration

CI runs on **GitHub Actions** ([.github/workflows/ci.yml](.github/workflows/ci.yml)):

- **Runner:** `windows-latest`. **Python matrix:** 3.11, 3.12, 3.13.
- **Triggers:** every pull request, and pushes to `main`.
- **Steps:** install uv → `uv sync --all-packages` → Ruff lint and format checks → `uv run pytest ConfigurationDeskMCP/tests`.

CI does not exercise a licensed ConfigurationDesk installation. Treat real COM automation as separate operational acceptance on a licensed machine.

### Pull-request workflow

- Branch from `main`; do not push to `main` directly. Open a PR.
- Keep PRs focused; update docs in the same PR as the code change.
- A review from a [CODEOWNERS](.github/CODEOWNERS) maintainer is required.
- CI must be green before merge.

---

## 7. Domain knowledge

This repository documents the **software**, not ConfigurationDesk itself. For domain questions such as COM API names, object hierarchies, and feature semantics, use the documentation delivered with your licensed ConfigurationDesk release.

When you add a domain capability, cite the manual title and section, or the exact API reference URL, in the COM wrapper docstring so the next contributor can verify it.

---

## 8. Licensing & governance

This project is licensed under Apache-2.0. See [LICENSE](LICENSE) and [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Ownership, contributor access, review, and release rules are defined in [GOVERNANCE.md](GOVERNANCE.md).

By contributing, you agree your contributions are licensed under Apache-2.0.

---

## 9. Conduct & security

- Be respectful - see the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security issues privately as described in [SECURITY.md](SECURITY.md); do **not** open a public issue for vulnerabilities.