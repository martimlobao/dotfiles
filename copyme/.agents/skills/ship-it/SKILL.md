---
name: ship-it
description: >-
  Use when the user asks an agent to turn local changes into a conventional
  commit, create a branch, push it, and open a GitHub pull request.
---

# Ship It

## Overview

Create a reviewable GitHub PR from local changes without swallowing unrelated
work. Keep the commit conventional, the PR body concise, and SSH pushes
compatible with 1Password on macOS.

## Workflow

1. Inspect state before changing anything:
    - `git status --short --branch`
    - `git diff --stat`
    - `git diff --cached --stat`
    - `git log -1 --oneline`
2. Identify the intended change set. Stage only those paths. Do not use `git add .`
   when unrelated edits may exist. If scope cannot be determined from the request
   and diff, ask before staging.
3. Create or switch to a new descriptive branch before committing. Use the repo or
   user branch naming convention when one exists. If no convention exists, use
   `<type>/<short-slug>` where `<type>` matches the commit type, such as
   `fix/retry-api-timeouts`. Never commit directly on `main` or `master` unless
   the user explicitly asks.
4. Run the repo's required checks from `AGENTS.md`, `CLAUDE.md`, README, or package
   scripts when they are discoverable. If checks fail, stop before committing
   unless the user explicitly asked to commit despite failures.
5. Commit with conventional commit syntax:
    - header: `<type>: <short imperative summary>`
    - common types: `fix`, `feat`, `docs`, `test`, `refactor`, `chore`
    - body: short bullet lines, each starting lowercase after `-`
6. Push with plain Git:
    - first run `git push -u origin <branch>`
    - if upstream already exists, run `git push`
7. Open a GitHub PR. Use the commit header as the PR title and the commit body
   bullets as the PR body.

## Commit And PR Text

Use one commit unless the user asks for multiple commits.

Good commit shape:

```text
fix: retry transient api failures on timeout

- add exponential backoff with jitter for 5xx and network errors
- surface last error in logs when retries are exhausted
- add tests for retry limits and non-retryable status codes
```

Rules:

- Header must be conventional commit syntax.
- Header should be lowercase except proper nouns or required identifiers.
- Every body line must be a bullet.
- Every bullet description must start lowercase.
- PR title must match the commit header.
- PR body must use the same short lowercase bullets unless the user asks for a
  different body.

## 1Password SSH Pushes

Do not replace SSH push with `gh auth login` just because signing fails. On macOS
with 1Password SSH agent, sandboxed agent environments can block the agent socket
even when the user authorizes the prompt.

If `git push` fails with one of these symptoms:

- `sign_and_send_pubkey: signing failed`
- `communication with agent failed`
- `Error connecting to agent: Operation not permitted`
- `Permission denied (publickey)` after an agent/signing error

retry the same plain `git push` command outside the sandbox or with the platform's
elevated execution mode so OpenSSH can reach the configured `IdentityAgent`. When
available, use tool escalation such as:

```text
sandbox_permissions = "require_escalated"
justification = "Allow git push to run outside the sandbox so SSH can access the 1Password agent socket."
prefix_rule = ["git", "push"]
```

For diagnosis, run `ssh -G git@github.com` to confirm `identityagent` points at
the 1Password socket, and run `ssh -T git@github.com` outside the sandbox if
authentication still fails. If it still fails outside the sandbox, report the
exact command and stderr instead of changing remotes or auth methods.

## PR Creation

Prefer the GitHub connector when available. Otherwise use `gh pr create`
non-interactively with explicit title/body/head/base. If `gh` is unauthenticated,
ask for GitHub auth before retrying; do not run a browser login flow without
telling the user why.

Use the remote default branch as the PR base when discoverable. If not discoverable, use `main`.

## Final Response

Report:

- branch name
- commit hash and header
- PR URL
- verification commands and results
- any skipped checks or known blockers

If the host platform supports git status directives or PR cards, emit them only
after the corresponding operation succeeds.
