---
name: kitty-bump-version
description: |
  Cut a SemVer release for a project that derives its version from git tags (uv-dynamic-versioning, hatch-vcs, setuptools-scm). Picks the next version from commits since the previous tag, creates the annotated tag, pushes it, and optionally drives a `release: published` GitHub Actions publish workflow via `gh release create`. Use when the user says "cut a release", "bump the version", "tag vX.Y.Z", "publish to PyPI", or "/kitty:bump-version".
when_to_use: |
  Triggers: "release", "bump version", "cut a release", "tag vX.Y.Z", "publish to PyPI", "/kitty:bump-version". Only applies to projects with dynamic VCS-derived versioning — refuses to edit a hardcoded `version =` field. Skip when the user just wants to add a tag manually with no version-bump heuristic.
argument-hint: '[major|minor|patch|vX.Y.Z] [--no-push] [--no-release]'
allowed-tools:
- Bash
- Read
- Grep
metadata:
  short-description: Tag-driven SemVer release for VCS-versioned Python projects.
---

Cut a release for the current repository.

## Preconditions

Before doing anything, verify these and bail with an explanation if any fail:

1. The working tree is clean (`git status --porcelain` empty).
2. The current branch is the release branch (look at `pyproject.toml` /
   `CONTRIBUTING.md` / `CLAUDE.md`; default to `main` if unspecified). Reject
   other branches unless the user passes an explicit override.
3. Local branch is up to date with `origin/<branch>` (`git fetch` then compare
   `git rev-parse HEAD` to `git rev-parse @{u}`).
4. The project uses VCS-derived versioning. Confirm one of:
   - `pyproject.toml` declares `dynamic = ["version"]` AND has either
     `[tool.uv-dynamic-versioning]`, `[tool.hatch.version] source = "vcs"`,
     or a `setuptools-scm` config.
   - `package.json` has a release-please / changesets setup.
   If none of these exist, surface that to the user and stop — this skill
   does not edit a hardcoded `version = "x.y.z"` field.

## Pick the next version

1. Read the most recent semver tag: `git tag -l "v[0-9]*" --sort=-v:refname | head -1`.
2. If `$ARGUMENTS` is `major|minor|patch`, bump from that tag using SemVer.
   If `$ARGUMENTS` is `vX.Y.Z`, use that exact version.
   Otherwise, propose a bump level based on the commits since the tag (look
   at the subjects of `git log <last-tag>..HEAD --format=%s`):
   - Any `feat!:`, `BREAKING CHANGE:`, MCP-tool removal, schema change → MAJOR
   - Any `feat:`, new language, new skill, new migration → MINOR
   - Only `fix:`, `chore:`, `docs:`, dependency bumps → PATCH
   Then ask the user to confirm via AskUserQuestion (skip the prompt when
   running in a pipeline mode like `kitty:lfg` and pick the recommended
   option silently).

## Tag and push

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — <one-line summary>"
git push origin vX.Y.Z
```

Skip the `git push` when `--no-push` is passed.

## Trigger publish (optional)

If `.github/workflows/publish.yml` (or similar) is wired to
`on: release: types: [published]`, create a GitHub release so the workflow
fires:

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z" \
  --notes "$(git log <previous-tag>..vX.Y.Z --format='- %s')"
```

Skip this step when `--no-release` is passed or when `gh` is not available.

## Report

Print the tag, the publish-workflow URL (if any), and the resolved version
string. For uv-dynamic-versioning, also run
`uv run python -c "import importlib.metadata as m; print(m.version('<pkg>'))"`
after the tag is created so the user can verify the version resolves
correctly.

## Notes

- Never amend or move an existing release tag — cut a new patch instead.
- Force-pushing the release branch (or moving a tag with `-f`) is destructive;
  refuse unless the user explicitly asks.
