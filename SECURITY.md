# Security Policy

## Supported scope

This project is a local-first public-source research CLI. It reads public YouTube data through user-run tooling and writes local files under the project instance you choose.

The project is best-effort and depends on YouTube behavior plus `yt-dlp` extractor support. Availability of metadata, transcripts, comments, and snapshots is not guaranteed.

## Sensitive data boundary

Do not commit or publish:

- generated transcripts, comments, snapshots, reports, caches, or databases;
- private watchlists and target lists;
- cookies, browser profiles, API keys, tokens, `.env` files;
- customer/client/project-specific research notes.

The default `.gitignore` excludes common generated and secret-bearing paths, but you remain responsible for reviewing what you commit.

## Reporting vulnerabilities

Preferred: use GitHub's private vulnerability reporting / GHSA flow if it is enabled for this repository.

If private reporting is unavailable, open a minimal GitHub issue that describes the class of problem without including secrets, private datasets, cookies, tokens, or generated evidence. Do not paste sensitive values into public issues.

## Out of scope

- YouTube rate limits, extractor instability, removed videos, unavailable subtitles/comments, regional differences, or `yt-dlp` upstream behavior.
- Requests to bypass access controls, authentication, age gates, geo restrictions, paywalls, or platform policies.
- Reports generated from private user datasets or private watchlists outside this public repository.
