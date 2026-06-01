# Security Policy

## Supported scope

This project is a local-first public-source research pipeline. It reads public YouTube data through user-run tooling and writes local files under the project instance you choose.

## Sensitive data boundary

Do not commit or publish:

- generated transcripts, comments, snapshots, reports, caches, or databases;
- private watchlists and target lists;
- cookies, browser profiles, API keys, tokens, `.env` files;
- customer/client/project-specific research notes.

The default `.gitignore` excludes common generated and secret-bearing paths, but you remain responsible for reviewing what you commit.

## Reporting

For security issues in this repository, open a GitHub issue with a minimal reproduction and do not include secrets or private datasets.
