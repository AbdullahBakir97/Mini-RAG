# Security Policy

## Supported Versions

This project follows a single-stream development model on the default branch.
Only the latest released or default-branch revision is supported.

## Reporting a Vulnerability

If you discover a security issue, please **do not open a public issue**.
Instead, contact the maintainer directly:

- Email: abdullah.bakir.1997@gmail.com
- GitHub: [@AbdullahBakir97](https://github.com/AbdullahBakir97)

You will receive an acknowledgement within a reasonable time, and a fix
or mitigation will be coordinated before any public disclosure.

## Checks on every change

- CI checks the Python and npm dependencies against known vulnerabilities
  (`pip-audit`, `npm audit`) and the whole git history for committed
  secrets (`gitleaks`); Dependabot proposes dependency upgrades weekly.
- See [Architecture](../docs/architecture.md) for how tenants are kept
  apart, how API keys are stored (only their SHA-256) and how uploads,
  webhooks and the chat widget are restricted.

_Last updated: 2026-05-04_
