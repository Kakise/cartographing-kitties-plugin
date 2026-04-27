---
title: Shared / Remote Graph Cache (R8)
type: feat
status: active
date: 2026-04-23
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
parent: docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md
requirement: R8
---

# Shared Graph Cache — Implementation Plan (R8)

## Overview

Let a team member publish a `.pawprints/graph.db` artifact to a shared location (HTTP URL, S3,
or a git-tracked compressed file) so teammates pull it on first install instead of re-indexing
from scratch. Cold onboarding on large monorepos drops from minutes to seconds. Ships as two
MCP tools and a CLI. Zero new service dependencies — artifact-based by default.

## Problem Frame

First-time indexing on a large monorepo can take tens of minutes (annotation dominates). Every
new engineer pays this cost, and CI environments pay it per job. Cursor's shared-team-indexing
UX has normalized the expectation of a prewarmed graph. The brainstorm scopes this as
artifact-first (simple, no service) with pull-from-URL as the second mode.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R8.a — `publish_graph` tool: dump + compress + upload the graph | Unit 1 |
| R8.b — `pull_graph` tool: download + verify + install | Unit 2 |
| R8.c — Commit-SHA + graph-version metadata in artifact for staleness checks | Unit 3 |
| R8.d — CLI wrappers (`uv run python -m cartograph.sharing publish/pull`) | Unit 4 |
| R8.e — Optional author-email stripping before publish (privacy) | Unit 5 |

## Scope Boundaries

- **In scope:** artifact format, publish/pull for HTTP + S3-compatible endpoints + local file
  paths, staleness detection, privacy stripping of author-email data from R4.
- **Out of scope:** a hosted Cartograph service; delta / incremental shared updates (full
  artifact swap only for v1); access control (assume users wrap auth at the transport layer).

## Context & Research

### Artifact Format

- Filename: `graph-<project-slug>-<commit-sha>.car` (suffix mnemonic for Cartograph).
- Content: gzipped `tarball` containing:
  - `graph.db` (the SQLite file; VACUUM'd before archiving for size).
  - `memory.db` (the litter/treat-box file — optional, included by default, excluded via
    `--no-memory`).
  - `manifest.json` with:
    - `cartograph_version` (current plugin version).
    - `schema_version` (from `graph_meta`).
    - `commit_sha` (the git commit indexed against, from R4 if available, else `None`).
    - `indexed_files_count`, `nodes_count`, `edges_count` — for UX surface on pull.
    - `created_at`.
    - `author_emails_stripped: bool` — set by Unit 5.
- Target size: a large real-world repo (~10K nodes) yields ~10–30 MB gzipped.

### Transport Layer

- **Local file:** `file:///path/to/out.car` — just a copy. Useful for `scp` / NFS / shared drives.
- **HTTP(S):** `PUT`/`GET` against a URL. Simple auth via `Authorization` header from
  `KITTY_SHARED_CACHE_TOKEN` env var.
- **S3-compatible:** URL scheme `s3://bucket/key`; uses `boto3` if installed, or falls back to
  the AWS CLI via subprocess. `boto3` is an optional dependency.
- **Git-tracked:** add the `.car` file directly to the repo under `.pawprints/shared/`; pull is a
  `git pull`. Document but don't build special support — it's just "copy file, git add, git
  push", which the user does manually.

### Staleness Detection

On pull:
1. Compare artifact's `commit_sha` with `git rev-parse HEAD`.
2. If mismatch, run `git diff --name-only <artifact_sha>..HEAD` to enumerate changed files.
3. Install the artifact, then call `Indexer.index_changed(paths=changed_files)` to catch up.
4. Emit a summary: "Pulled graph at commit X; re-indexed Y files to reach Z."

## Key Technical Decisions

### Artifact is authoritative, not additive

On pull, the existing local `graph.db` is **replaced** (after backup to
`.pawprints/graph.db.bak-<timestamp>`). Merging partial graphs is error-prone and an explicit
non-goal for v1.

### Publish is explicit

`publish_graph` **never** runs automatically. The user or a CI job invokes it. No background
push. Avoids surprising data egress.

### Privacy-by-default for shared caches

When `KITTY_HISTORY_ENABLED=true` at publish time, the `publish_graph` tool offers an
`strip_author_emails=True` parameter that:
1. Replaces `author::<email>` qualified names with `author::<sha256(email)[:8]>`.
2. Clears the `summary` on those nodes.
3. Removes `properties.author_email` from `authored_by` edges.

Decision: **default to `strip_author_emails=True`**. Users opting into sharing typically want
the insights, not the PII exposure. Overridable for internal single-tenant setups.

## Open Questions

### Resolve Before Implementing

- **Do we version the artifact format itself?** Recommend: yes — `manifest.json` includes
  `artifact_version: 1`. Future breaks gracefully; old clients reading v2 print a clear error.
- **Is `boto3` a soft dependency or not included at all?** Recommend: soft. Make the S3 path
  optional; document "install with `uv add boto3`" if the user needs it. HTTP + local cover the
  90% case.

### Defer

- Incremental artifact deltas ("only files changed since artifact X"). Wait for user feedback.
- Multi-tenant caches keyed on repo URL hash. Wait for evidence that teams want per-project vs.
  per-monorepo slicing.

## Implementation Units

### Unit 1 — `publish_graph` tool

- [ ] `src/cartograph/sharing/__init__.py`, `src/cartograph/sharing/artifact.py` — artifact
      pack/unpack primitives.
- [ ] `src/cartograph/sharing/artifact.py::pack_graph(storage_root, commit_sha, strip_author_emails
      ) -> Path` — VACUUM DB copy, tar+gzip, write `manifest.json`.
- [ ] `src/cartograph/sharing/transport.py::upload(path, destination)` — dispatches by URL
      scheme (`file://`, `http(s)://`, `s3://`).
- [ ] `src/cartograph/server/tools/sharing.py::publish_graph(destination: str, include_memory:
      bool = True, strip_author_emails: bool = True) -> {artifact_path, size_bytes,
      manifest}`.

**Files:** `src/cartograph/sharing/__init__.py`,
`src/cartograph/sharing/artifact.py`, `src/cartograph/sharing/transport.py`,
`src/cartograph/server/tools/sharing.py` (all new).

**Test scenarios:**
- Happy: publish to `file:///tmp/test.car` → file exists, round-trips through `pack_graph` +
  `unpack_graph`.
- Happy: `strip_author_emails=True` → unpacked graph has hashed author nodes.
- Edge: destination write fails → local artifact remains in `.pawprints/publish/` for retry;
  no partial remote state.
- Edge: S3 path without `boto3` installed → clear error message.

### Unit 2 — `pull_graph` tool

- [ ] `src/cartograph/sharing/transport.py::download(source, destination_path)`.
- [ ] `src/cartograph/sharing/artifact.py::unpack_graph(artifact_path, storage_root)` — extract
      to a temp dir, verify manifest, back up existing `graph.db`, move files into place.
- [ ] `src/cartograph/server/tools/sharing.py::pull_graph(source: str,
      skip_staleness_catchup: bool = False) -> {pulled_commit_sha, artifact_commit_sha,
      reindexed_files_count, manifest}`.
- [ ] Staleness catch-up: if commit SHA mismatches and staleness catch-up is enabled, run
      `Indexer.index_changed` on the diff.

**Test scenarios:**
- Happy: pull from `file:///tmp/test.car` → local `graph.db` replaced, backup created.
- Happy: stale artifact (repo is N commits ahead) → catch-up indexes the delta.
- Edge: artifact_version mismatch → clear error, no destructive install.
- Edge: network failure mid-download → temp file discarded, local state untouched.
- Edge: `skip_staleness_catchup=True` → even stale graphs install without re-indexing, with a
  clear warning in the return value.

### Unit 3 — Manifest + versioning

- [ ] `src/cartograph/sharing/manifest.py` — `Manifest` dataclass + (de)serialization.
- [ ] `manifest.json` schema documented inline.
- [ ] `pack_graph` writes the manifest; `unpack_graph` verifies it (version compatibility check,
      schema_version check).

**Files:** `src/cartograph/sharing/manifest.py` (new).

### Unit 4 — CLI

- [ ] `python -m cartograph.sharing publish <destination> [--no-memory] [--keep-author-emails]`.
- [ ] `python -m cartograph.sharing pull <source> [--skip-staleness-catchup]`.
- [ ] Both shell out to the tool functions for consistency; identical behavior.

**Files:** `src/cartograph/sharing/__main__.py` (new).

### Unit 5 — Privacy strip helper

- [ ] `src/cartograph/sharing/privacy.py::strip_author_emails(conn)` — in-memory SQL update over
      a *copy* of the DB (never the live one):
      - Hash emails in `nodes.qualified_name`, `nodes.summary`.
      - Clear `properties` field on `authored_by` edges.

**Files:** `src/cartograph/sharing/privacy.py` (new).

**Test scenarios:**
- Happy: author nodes get hashed names; original DB untouched.
- Edge: no `authored_by` edges in graph (R4 not shipped) → no-op.

### Unit 6 — Documentation

- [ ] Update `README.md` with Sharing section: artifact format, CLI usage, privacy defaults.
- [ ] Update `CLAUDE.md` MCP tools table.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md`.

## System-Wide Impact

- **Plugin surface:** +2 MCP tools + 1 CLI entrypoint.
- **Dependencies:** +optional (`boto3` for S3 only).
- **First-install UX:** opt-in, gated on a shared URL existing. No behavior change for solo users.
- **Storage:** `.pawprints/publish/` and `.pawprints/graph.db.bak-<timestamp>` — users can clean
  up manually; we don't auto-delete backups (give them a "get out of jail free" artifact).

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| A corrupted artifact breaks a teammate's setup | Backup-then-install; verification via manifest before overwrite; hash-check the DB file |
| Users accidentally publish an artifact with PII | Default `strip_author_emails=True`; require explicit opt-out |
| Stale artifact makes search results misleading | Staleness catch-up by default; clear warning if `skip_staleness_catchup=True` |
| Transport auth fails silently | HTTP 4xx/5xx raise; S3 credentials missing raises clearly |

**Dependencies:** benefits from **R4** (commit-history metadata in manifest) but doesn't require
it. Artifact still works without `commit_sha`; staleness check then falls back to hash-based
diff.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R8)
- Parent roadmap: `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`

## Handoff

Ready for `kitty:work`. Entry point: Unit 3 (manifest format) so Units 1 and 2 can build on a
stable contract. Units 1 and 2 then parallelize. Units 4–6 are wrap-up.
