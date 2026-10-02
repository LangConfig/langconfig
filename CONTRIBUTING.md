# Contributing to LangConfig

Thank you for your interest in contributing to LangConfig! We welcome contributions from everyone.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Style Guidelines](#style-guidelines)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment (see [Development Setup](#development-setup))
4. Create a branch for your changes
5. Make your changes
6. Test your changes
7. Submit a pull request

## How to Contribute

There are many ways to contribute to LangConfig:

- **Report bugs** - If you find a bug, please report it by opening an issue
- **Suggest features** - Have an idea? Open an issue to discuss it
- **Improve documentation** - Help us improve our docs
- **Write code** - Fix bugs or implement new features
- **Review pull requests** - Help review other contributors' work
- **Add agent templates** - Create new pre-built agent configurations
- **Create tool integrations** - Add new MCP server integrations

## Development Setup

The complete, tested onboarding path is in [docs/SETUP.md](docs/SETUP.md).

### Prerequisites

- Node.js `^20.19.0` or `>=22.12.0` with npm 10+
- Python 3.11-3.13 (Python 3.12 recommended)
- Docker with Compose v2
- Git

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/langconfig.git
cd langconfig

# Create an isolated Python environment and configure the app
python -m venv .venv
# Activate .venv using the command for your shell; see docs/SETUP.md
npm ci
python backend/scripts/setup.py
python -m pip install -r backend/requirements-dev.txt
```

### Running in Development

```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend
npm run dev
```

## Pull Request Process

1. **Create a branch** from `main` with a descriptive name:
   - `codex/add-new-agent-template`
   - `codex/fix-workflow-execution`
   - `codex/update-setup-docs`

   For dependent changes, branch from the preceding feature branch and identify
   that base in the PR. Keep each branch buildable and document the intended
   merge order. Pushes to `main` and `codex/**`, all PRs, and manual dispatches
   run CI; a newer run on the same ref cancels the older run.

2. **Make your changes** following our style guidelines

3. **Test your changes** using the active Python 3.12 environment:
   ```bash
   # Run from the repository root
   python -m ruff check .
   npm run lint
   npm run format:check
   npm run typecheck
   npm run build
   npx playwright install chromium
   npm run test:hermes
   ```

   For backend tests, first configure both database URLs to the same disposable
   test database and create it as described in [Quality gates](docs/QUALITY_GATES.md).
   Then run `python -m pytest -q --ignore=tests/test_playwright_tools.py` from
   `backend/`. Test fixtures rebuild that database's schema.

   `test:hermes` exercises the real Hermes component in Chromium with mocked
   APIs. Install Chromium once after setup or a Playwright version change.

   Biome and Ruff currently check the explicit files listed in their configs;
   TypeScript checks the application. Run `npm run format` to apply formatting
   to the Biome scope. Expand lint scopes with the feature branch that cleans
   those files. See [Quality gates](docs/QUALITY_GATES.md) for the exact scope,
   commands, and checks deferred to later branches.

4. **Commit your changes** with clear, descriptive messages:
   ```
   Add new SQL analysis agent template

   - Added SQLAnalysisAgent with query optimization capabilities
   - Includes support for PostgreSQL and MySQL dialects
   - Added unit tests for query parsing
   ```

5. **Push to your fork** (or `origin` for repository collaborators) and create a pull request

6. **Fill out the PR template** describing:
   - What changes you made
   - Why you made them
   - How to test them
   - The base branch and dependent branches, if any
   - Configuration, schema, or migration changes and upgrade instructions
   - Commands actually run, their results, and anything not verified

7. **Address review feedback** if requested

### PR Requirements

- All tests must pass
- Code should follow the style guidelines
- Documentation should be updated if needed
- Commits should be atomic and well-described

## Style Guidelines

### Python (Backend)

- Follow PEP 8
- Use type hints
- Preferred line length: 120 characters; the initial Ruff rules check errors and
  unused names, not formatting or line length
- Use docstrings for functions and classes

```python
def process_workflow(
    workflow_id: str,
    config: WorkflowConfig,
    timeout: int = 300
) -> WorkflowResult:
    """
    Process a workflow execution.

    Args:
        workflow_id: Unique identifier for the workflow
        config: Workflow configuration object
        timeout: Maximum execution time in seconds

    Returns:
        WorkflowResult containing execution output and metrics
    """
    ...
```

### TypeScript (Frontend)

- Use TypeScript strict mode
- Prefer functional components with hooks
- Use descriptive variable names
- Export types/interfaces

```typescript
interface WorkflowNodeProps {
  id: string;
  data: NodeData;
  onUpdate: (id: string, data: Partial<NodeData>) => void;
}

export const WorkflowNode: React.FC<WorkflowNodeProps> = ({
  id,
  data,
  onUpdate
}) => {
  // ...
};
```

### Git Commits

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep first line under 72 characters
- Reference issues when applicable: `Fix #123`

## Reporting Bugs

When reporting bugs, please include:

1. **Description** - Clear description of the bug
2. **Steps to reproduce** - How to trigger the bug
3. **Expected behavior** - What should happen
4. **Actual behavior** - What actually happens
5. **Environment** - OS, browser, Node/Python versions
6. **Screenshots/logs** - If applicable

Use the bug report issue template when available.

## Suggesting Features

When suggesting features:

1. **Check existing issues** - Your idea may already be proposed
2. **Describe the problem** - What problem does this solve?
3. **Describe the solution** - How should it work?
4. **Consider alternatives** - What other approaches exist?
5. **Additional context** - Mockups, examples, etc.

Use the feature request issue template when available.

## Questions?

If you have questions, feel free to:
- Open a GitHub Discussion
- Check existing issues and discussions
- Review the documentation

Thank you for contributing to LangConfig!
