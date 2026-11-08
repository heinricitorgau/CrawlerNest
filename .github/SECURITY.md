# Security policy

## Reporting a vulnerability

**Do not open a public issue, pull request or discussion for a security vulnerability.**

Report it privately through GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Describe the problem, the affected component (pipeline, Spring Boot API, Next.js web, agent API), the steps to
   reproduce it, and the impact you expect.

Only the maintainers can see the report. We will reply in the advisory, work on a fix there, and credit you when the
advisory is published unless you ask us not to.

## Supported versions

Only the latest commit on `main` receives security fixes.

## Scope

In scope: the code in this repository -- the crawlers and pipeline, the API on port 8080, the web app on port 3000,
the agent API on port 8090, and the Docker and deployment files in `deploy/`.

Out of scope: the development defaults in the documentation (the `test`/`test` PostgreSQL account is meant for a local
machine only), and the third-party sites the crawlers read.
