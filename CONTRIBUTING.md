# Contributing to ClaudeState

Thanks for your interest in improving ClaudeState.

## Development Setup

```bash
git clone https://github.com/benslimanh/claudestate
cd claudestate
pip install -e ".[dev]"
```

Run quality checks before opening a PR:

```bash
ruff check claudestate/
mypy claudestate/ --ignore-missing-imports
pytest tests/ -v
```

## Pull Request Guidelines

- Keep PRs focused on one change.
- Add or update tests when behavior changes.
- Update docs when CLI behavior or flags change.
- Use clear commit messages.

## Reporting Issues

Use GitHub issue templates for bug reports and feature ideas.
Include reproduction steps, expected behavior, and actual behavior.

## Good First Contributions

- Improve CLI help and docs clarity
- Add tests for command edge cases
- Add language-detection heuristics
- Improve loop-check diagnostics
