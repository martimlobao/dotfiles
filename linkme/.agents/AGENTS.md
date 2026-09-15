# AGENTS.md

I'm Martim. You're my agent. We will be working together a lot, so I thought it would be worth
introducing myself.

I love to build. I focus on building complex things as simple as possible. I love to find ways to
reduce complexity when solving problems.

I wanted to share some of my preferences here so we can be more aligned as we work together.

## Coding preferences (General)

- Keep things simple. Channel "yagni" energy unless told otherwise.
- Typesafety is useful, take advantage of it.
- Don't be scared to propose bold ideas if they can meaningfully benefit our work.
- Be careful with destructive actions that are not explicitly requested by the user.
- Tests are good! Endless smoke tests, "regression tests" for feature deletions, etc, much less
  good. Tests should be focused, not slop.
- Comments are useful for clarifying things which are not obvious from the code itself. They should
  mainly be used to explain the *why*, not the how. Good code should usually be self-explanatory,
  but when necessary feel free to describe (concisely) some behavior, functionality, weird edge
  case, etc.
- Keep comments up to date! When making changes, it's important to keep things in sync.

### Coding preferences (Python focused)

- Untyped code and freeform strings are bad. Constraints are good. Loose dictionary objects are
  unlintable, strict dataclasses or pydantic objects ensure consistency. `ty` is a good library for
  type checking.
- Unless required by a specific project, always use `uv`, never use `python` directly, and never
  ever use `pip` or `poetry`.

### Coding preferences (Typescript focused)

- `any` is the enemy. Inferred types are our friend. Our systems should adapt to changes, instead
  of requiring changes everywhere.
- If your TS code looks like a Python dev wrote it, it is bad TS code.
- Avoid one-line functions that are just casting wrappers.
- If not already specified in project, I generally like to use the following tech: Convex,
  Tailwind, React, Vite, pnpm (or bun).
- When uncertain, prefer: Tailwind, TypeScript, Bun, React, Convex, Clerk, Vercel.
- Focus on checking commands like `bun run typecheck`, `bun run lint`, etc.

## Questions are read-only

- A question is a request for an answer, not for changes. If the message opens with "how hard would
  it be", "what are your thoughts", "why does", "should we", "is it possible", "can X do Y", or
  otherwise asks rather than instructs: answer it, and do not edit files.
- If the answer is obvious and the change is trivial, still answer first and offer the change. Ask
  before making it.

## Match ceremony to the task

- Don't use more intelligent (and expensive) models for implementation work; those models should be
  reserved for thinking and planning and should then orchestrate and delegate implementation and
  exploration to more inexpensive models. Don't ask the CTO to do the intern's job.
- Do not spawn subagents or a multi-agent panel for work a single agent finishes in one pass.
  Delegation is for breadth or adversarial review, not for ordinary tasks.
- When several agents do work in parallel, state file ownership up front so they do not collide.
- If asked to do too much work at once, stop and state that clearly.

## Picking the Right Models for Workflows and Subagents

Rankings, higher = better. Cost reflects what I actually pay (OpenAI is near-free for me due to a
deal), not list price. Intelligence is how hard a problem you can hand the model unsupervised.
Taste covers UI/UX, code quality, API design, and copy.

| model         | cost | intelligence | taste |
| ------------- | ---- | ------------ | ----- |
| gpt-5.6-luna  | 10   | 2            | 2     |
| gpt-5.6-terra | 8    | 5            | 5     |
| gpt-5.6-sol   | 4    | 7            | 7     |
| gpt-6-astra   | 2    | 9            | 8     |
| sonnet-5      | 5    | 4            | 7     |
| opus-5        | 4    | 6            | 8     |
| fable-5.1     | 1    | 8            | 9     |

How to apply:

- These are defaults, not limits. You have standing permission to override them: if a cheaper
  model's output doesn't meet the bar, rerun or redo the work with a smarter model without asking.
  Judge the output, not the price tag. Escalating costs less than shipping mediocre work.
- Don't let cost prevent you from using the right model for the job. Instead, take advantage of
  cheaper options to get more information and try things before moving the work to a more expensive
  option.
- Bulk/mechanical work (clear-spec implementation, data analysis, migrations): gpt-5.5 - it's
  effectively free.

## Blast radius

- Never touch production, live databases, or daily-driver build/preview channels unless explicitly
  told to or by requesting explicit permission. When a task is adjacent to any of them, name what
  you are about to touch before touching it.

## Pull Requests

- PR titles usually become commit messages, so follow the repository's title conventions. Look at
  recently merged PRs and Git history for examples. Prefer a concise, human-readable title that
  explains why the change matters:

  ```text
  BAD
  > ❌ perf(server): negotiate permessage-deflate on the websocket

  GOOD
  > ✅ perf(server): cut websocket frame size by 70%+ with gzipping
  ```

- PR descriptions should aim for simplicity. Open with a minimal, clear description of the problem.
  Follow up with how you solved it. Do not lead with an implementation inventory:

  ```text
  BAD
  > ❌ Removed implicit workspace carry-over from every "new thread" entry point (cmd+n / cmd+shift+o, sidebar v1/v2 buttons, command palette). New threads inherit only the project from context; branch, worktree, and env mode always come from the configured defaults. Deleted buildContextualThreadOptions, startNewThreadInProjectFromContext, and the v1 sidebar's seed-context machinery.

  GOOD
  > ✅ My "new worktree" default was ignored when starting new threads on existing worktrees. Super unintuitive. Now your preferences always apply.
  ```

  Do not mention files not included in the PR itself, e.g. "`make check` succeeded with only
  unrelated unstaged settings file need linting".
- Add a blurb to the end of the PR description about what model and harness is making the changes,
  e.g. "Model: GPT-5.6-Sol // Harness: Codex". Do not include this blurb as another bullet in the
  PR description itself.
- **Open a real PR, not a draft.** Drafts do not get review-bot coverage.
- **Rebase onto latest `main` before opening.** Stale branches conflict and waste a review round.
- When asked to monitor or babysit a PR: poll checks and comments newer than the last push; verify
  each bot finding against the source before acting on it; fix real ones and dismiss false
  positives with a written reason; fix CI failures, distinguishing real breaks from known infra
  flakes. If nothing is new, stay quiet — do not post filler comments. Stop when the repo's review
  bots are green on the latest commit.
- Merge only per the disposition given in the request (merge when green, or stop and report). If
  none was given, report and ask.
