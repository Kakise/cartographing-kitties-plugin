---
title: Optimize Extension for Gemini CLI
type: refactor
status: superseded
date: 2026-04-04
superseded_by: docs/plans/2026-04-21-002-refactor-codex-plugin-alignment-plan.md
---

## Overview
This plan outlines the steps required to optimize the `kitty` extension for the Gemini CLI environment, migrating it from its original Claude Code origins. The goal is to align the extension's structure, tool syntax, and configuration files with Gemini CLI's expected schema and best practices.

## Problem Frame
The current extension works partially but contains Claude-specific syntax and redundant files. Specifically:
- **Subagents (`plugins/kitty/agents/*.md`)** use Claude's tool names (`Read, Grep, Glob, Bash`) instead of Gemini's (`read_file, grep_search, glob, run_shell_command`).
- **Commands (`plugins/kitty/commands/`)** contain redundant `.md` files, which are Claude-specific, whereas Gemini CLI relies solely on the `.toml` format for commands.
- **Skills (`plugins/kitty/skills/`)** contain references to Claude Code features like `AskUserQuestion`.
- **Manifest & Documentation** reference Claude Code and don't take full advantage of Gemini's configuration (e.g., `contextFileName`).

## Requirements Trace
- Ensure Gemini CLI fully parses the `gemini-extension.json` manifest.
- Update subagent tool definitions to use Gemini CLI's standard `snake_case` tool names.
- Clean up redundant Claude-specific command files (`.md` in commands directory).
- Update `GEMINI.md` and SKILL files to refer to Gemini CLI terminology rather than Claude Code.

## Scope Boundaries
- **In Scope:** Modifying `gemini-extension.json`, updating YAML frontmatter in `plugins/kitty/agents/*.md`, removing `.md` files in `plugins/kitty/commands/`, updating `GEMINI.md` and `.md` files in `plugins/kitty/skills/` to remove Claude-specific references.
- **Out of Scope:** Altering the core Python logic (`src/cartograph/`) or rewriting the MCP server implementation. We are focusing purely on the extension configuration side.

## Key Technical Decisions
1. **Tool Syntax:** Subagent definitions will be updated to `tools: [read_file, grep_search, glob, run_shell_command, "mcp_kitty_*"]` to properly grant them the necessary permissions in Gemini CLI.
2. **Commands Cleanup:** Only `.toml` files will be kept in `plugins/kitty/commands/` as Gemini CLI automatically discovers commands defined in `.toml` format.
3. **Context Management:** `gemini-extension.json` will be updated to explicitly set `"contextFileName": "GEMINI.md"`.

## Implementation Units

- [ ] **Unit 1: Clean up Commands Directory**
  - Delete `kitty-explore.md`, `kitty-index.md`, and `kitty-status.md` in `plugins/kitty/commands/`.
  - Ensure the remaining `.toml` files are correctly formatted for Gemini CLI.

- [ ] **Unit 2: Update Subagents Tool Definitions**
  - Modify `tools` list in all `plugins/kitty/agents/*.md` files.
  - Replace `Read, Grep, Glob, Bash` with `[read_file, grep_search, glob, run_shell_command, "mcp_kitty_*"]`.
  - Remove or update any Claude-specific frontmatter (e.g., `color`).

- [ ] **Unit 3: Update SKILL instructions**
  - Search and replace mentions of "Claude Code" or "AskUserQuestion" in `plugins/kitty/skills/**/*.md`.
  - For example, in `kitty-brainstorm/SKILL.md`, change `(AskUserQuestion in Claude Code)` to standard blocking question tools.

- [ ] **Unit 4: Update Manifest and Context**
  - Update `plugins/kitty/gemini-extension.json` to include `"contextFileName": "GEMINI.md"`.
  - Update `GEMINI.md` to remove references to "Claude Code plugin" and rephrase to "Gemini CLI extension".

## System-Wide Impact
This will ensure that Gemini CLI's subagents can correctly load their required tools, allowing parallel workflows like `kitty:plan` and `kitty:work` to execute properly without tool invocation errors.

## Risks & Dependencies
- **Risk:** Removing Claude-specific files might break compatibility if the user intends to maintain a dual-compatible plugin.
- **Mitigation:** The `.claude-plugin` directory is untouched, so Claude Code can still function using its own manifest, but its commands might break if we remove the `.md` files. We can ask the user if they want to drop Claude support or maintain dual-compatibility.

## Open Questions
- Does the user want to completely drop Claude Code support, or maintain dual compatibility? If dual compatibility is needed, we should restore/keep the `.md` command files.