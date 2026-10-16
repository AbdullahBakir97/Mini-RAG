# Contributing

Thanks for considering a contribution!

## Quick path

1. Fork the repository.
2. Create a topic branch: `git checkout -b feature/short-name`.
3. Make your change. Keep diffs focused — small PRs land faster.
4. Run the local checks before opening the PR (the same ones CI runs):
   ```bash
   pip install -r requirements-dev.txt
   ruff check .
   pytest
   ```
5. Open a pull request describing **what** changed and **why**.

## Style

- Keep code readable; use clear names over clever ones.
- Match the file's surrounding conventions.
- Keep commit messages concise, in the imperative mood
  (e.g. `Add export option`, not `added export option`).

## Reporting bugs

Open an issue with:
- A short title describing the problem.
- Steps to reproduce.
- What you expected vs. what happened.
- Environment (OS, Python/Node version, browser).

## Asking questions

Open a discussion or issue with the `question` label.

## Code of conduct

By participating you agree to abide by the
[Code of Conduct](./CODE_OF_CONDUCT.md).

_Last updated: 2026-05-04 — maintained by [@AbdullahBakir97](https://github.com/AbdullahBakir97)_
