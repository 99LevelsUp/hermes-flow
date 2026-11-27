# AGENTS.md

## Purpose

Hermes Agent tooling for running GitHub roadmaps: the `roadmap-issue-flow` skill (the owner's
process from idea to release), the automated issue triage and everything that keeps them running.
It is meant for any project of the owner (99LevelsUp), not only the EVƎ repositories.

The repository is a Hermes skill tap: every skill lives in `skills/<name>/` with its `SKILL.md`,
`references/` and `scripts/`.

## Language

**Everything in this repository is in English, without exception**: code, comments, strings,
documentation, commit messages, PR descriptions, issue titles and bodies. Only the conversation
with the owner is in his language (Czech).

## Source of truth and the live copies

This repository is the source of truth. Hermes runs live copies:

| In the repo | Live copy |
|---|---|
| `skills/roadmap-issue-flow/` | `~/.hermes/skills/software-development/roadmap-issue-flow/` |
| `skills/roadmap-issue-flow/scripts/issue-triage.py` | `~/.hermes/scripts/issue-triage.py` (cron scripts must be real files under `~/.hermes/scripts`; the scheduler rejects symlinks that point outside) |
| `hermes/cron/issue-triage.json` | the cron job in `~/.hermes/cron/jobs.json` |
| `hermes/triage-config.json` | `~/.hermes/data/issue-triage/config.json`: the projects and repositories triage serves |

- Never change a live copy by hand. Change the repo, go through the flow (issue, branch, PR,
  gates), merge, then run `tools/deploy.sh` on the main checkout.
- When Hermes learns something during a task and patches the live skill (`skill_manage`), the
  change is carried into this repo in a PR the same day. `tools/deploy.sh` refuses to overwrite a
  live copy that differs from the last deployed commit, so such drift cannot be lost silently.
- Lessons go into the skill, a test or a check in this repo, not into agent memory.

## Process

Work on this repository follows the skill it contains: `skills/roadmap-issue-flow/SKILL.md` and
`references/flow.md`. In short:

- Roadmap: GitHub project "Hermes flow" (user project of 99LevelsUp), the same fields as the EVƎ
  roadmap (Status, Priority, Product, Estimate, Next step, Milestone).
- One problem = one issue (`## What`, `## Why`, `Source:`), kind of work by issue type only
  (Bug / Feature / Task), label `idea` until the Ready gate.
- Each item or bundle: own branch and worktree, tests that fail without the fix, a PR with
  `Closes #N`, gates ce-simplify-code then ce-code-review (ce-doc-review for documents), green CI.
- Priority, milestones, merging, closing and releases are the owner's decisions.

## Checks

- `ruff check .` (configuration in `ruff.toml`)
- `python3 -m py_compile skills/*/scripts/*.py tools/*.py`
- `python3 -m unittest discover -s tests` (standard library only; the suite grows with issue "Tests
  and CI for the triage script"). New or changed code of the triage script comes with tests; parts
  without tests are still verified with `--dry-run --only <issues>` before deploying.

CI (`.github/workflows/ci.yml`) runs the same checks on every push and pull request.

## Security

- The triage script acts with the owner's GitHub token on public repositories. Read the
  "Untrusted input in every step" and "Automation pitfalls" sections of the skill before changing
  anything that reads issue text or writes to GitHub.
- Never commit tokens, `.env` values, `~/.hermes` state, ledgers or logs. Project and field IDs are
  not secrets.
