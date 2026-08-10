# eval-harness (Personal Project)

Personal project. SDLC pipeline commands are available but optional -- use as needed.

## Project Context
- Slug: `eval-harness`
- Type: Personal
- Phase: See `.project-config.yaml`

## Working Rules
- All SDLC slash commands are installed in `.claude/commands/` in this folder.
- Run all commands from this folder.
- Project-specific API keys go in `.claude/settings.local.json` only (gitignored).
- Commands auto-update on session start via the SessionStart hook.
- Use SDLC commands (`/intake`, `/ba`, `/arch`, `/dev`, `/qa`, etc.) for structured work.
- For automation-testing projects, run `/test-stack <stack-id>` (java-selenium, python-selenium, playwright-python, playwright-typescript) to scaffold a working test framework into `src/` -- re-runnable any time to switch stacks.

## MCP Isolation -- MANDATORY
The Gitea, Taiga, and Woodpecker MCP tools connect via a shared admin account that can see all
projects. Only ever read or write to the `gitea_repo`, `taiga_project`, and `woodpecker_repo`
values defined in `.project-config.yaml`. Never touch resources belonging to other projects.

## Quick Start
Run `/init` to see current phase status and next steps.
