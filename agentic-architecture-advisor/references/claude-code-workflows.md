# Claude Code Configuration & Headless/CI Workflows

Source grounding: CCA-F Domain 2 (Claude Code Configuration & Workflows, 20% of the exam).

## The CLAUDE.md hierarchy

Every new Claude Code session starts with no memory of the project; `CLAUDE.md` files are what get stitched into the session's system prompt. On boot, Claude Code walks up the directory tree from the current folder and merges every `CLAUDE.md` it finds. Three levels, three distinct purposes:

| Level | Path | Scope | Version control |
|---|---|---|---|
| User | `~/.claude/CLAUDE.md` | Every project on this machine, this person only | Never committed |
| Project | `<repo-root>/CLAUDE.md` | Everyone who clones the repo | Committed |
| Directory | `packages/api/CLAUDE.md` | Only when Claude touches that sub-package | Committed alongside that package |

**The single most common misconfiguration**: a rule meant for the whole team (e.g. "run lint before every commit," "we use bun, not npm") gets placed in the user-level file. It works for the person who wrote it and silently never reaches anyone else's clone. If a rule needs to be shared, it belongs in the project-level file at the repo root — full stop. Directory-level files are for rules that should only apply when Claude is actually working inside that specific sub-package (different lint config, different test runner, a different sub-team's conventions).

## Custom slash commands

A slash command is a reusable prompt, invoked as `/name`, defined by a markdown file in `.claude/commands/`. The file body is the prompt injected when the command runs. YAML frontmatter controls behavior:

- `allowed-tools` — restricts which tools the command can call. A `/review` command should typically be locked to read-only tools (`Read`, `Grep`, `Glob`) with no `Write`/`Edit`/`Bash` — a review command that can also modify files is a scope violation waiting to happen.
- `argument-hint` — the placeholder shown in the command picker, documenting what argument the command expects.

When reviewing a slash command, check whether its `allowed-tools` scope actually matches its stated purpose — the most common gap is a read-only-sounding command (review, audit, summarize) that was never restricted and technically retains write/bash access.

## Headless / CI usage

The `-p` flag runs Claude Code non-interactively with a baked-in prompt — no chat loop, one input, one output. Paired with a structured-output schema, this lets a pipeline ask Claude to review a PR (or any artifact) and get back JSON with named categories rather than free text.

**The architectural rule that matters most here**: the pipeline should fail the build only on categories the schema names explicitly (e.g. `security_violation`, `breaking_api_change`) — never on vague, unstructured "concern" text. A pipeline that fails whenever Claude expresses any hedge or caution produces so much noise that the team disables or ignores it within a week or two, and a review nobody trusts anymore is strictly worse than no automated review at all. This is the same vague-adjective root cause as in `prompt-and-structured-output.md`, just showing up in a CI gate instead of a prompt.

## Checklist when reviewing Claude Code config / CI setup

- [ ] Does any rule in `~/.claude/CLAUDE.md` actually need to be shared with the team? If so, move it to the project-level file.
- [ ] Do directory-level `CLAUDE.md` files exist only where scope genuinely differs from the project root, or are they duplicating project-level rules unnecessarily?
- [ ] Does each slash command's `allowed-tools` actually match its intended scope (read-only commands locked to read-only tools)?
- [ ] Does the CI/headless pipeline fail the build only on schema-named categories, or on any free-text expression of concern?
- [ ] Is the headless invocation paired with a structured-output schema, or is it parsing free text and hoping for a consistent format?
