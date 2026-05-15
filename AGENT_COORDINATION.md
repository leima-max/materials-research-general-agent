# Agent Coordination

This workspace may be shared by Codex and an OpenClaw Agent.

## Shared Goal

Advance the user's configured research workflow in parallel without overwriting each other's work.

## Default Rules

1. Check the target files before editing.
2. Prefer append-only or narrowly scoped patches for small and medium changes.
3. For existing files, check file state or hash before writing when practical.
4. Do not revert or overwrite changes made by another agent unless the user explicitly requests it.
5. Keep outputs in task-specific files under `output/` when possible.
6. Record durable decisions in `MEMORY.md` and daily progress in `memory/YYYY-MM-DD.md`.
7. After code, data, config, or plot changes, run a concrete verification step before reporting success.

## Suggested Work Split

- Codex: code implementation, data processing scripts, plotting pipelines, verification, documentation.
- OpenClaw Agent: OpenClaw-native skills, long-running task orchestration, workspace agent operations, and parallel execution where configured.

## Conflict Handling

If both agents need the same file, pause and define ownership first:

- one agent edits the file;
- the other reads, reviews, or writes a separate notes/output file;
- merge only after verification.

