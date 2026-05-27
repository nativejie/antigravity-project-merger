# Antigravity Project Merger

English | [简体中文](./README.md)

A local migration utility for cleaning up duplicate Antigravity projects and restoring historical conversations to the correct project.

> This is an unofficial local maintenance tool for Antigravity / Gemini project data.

## Overview

Antigravity may sometimes create multiple project records for the same local workspace.

This can make the project list messy and cause historical conversations to appear under duplicated or incorrect projects.

Antigravity Project Merger scans the local Antigravity project configuration, detects projects that point to the same workspace path, keeps one primary project, merges useful configuration from duplicates, and migrates related conversation records back to the correct project.

## Features

- Detect duplicate Antigravity projects by workspace path
- Select a primary project record automatically
- Merge project settings and permission grants
- Migrate historical conversation project references
- Handle old `outside-of-project` conversations when possible
- Create physical backups before migration
- Restore from backup if needed
- Preview changes with `--dry-run`
- Run non-interactively with `--force`

## Requirements

```txt
Python 3.8+
```

No third-party Python packages are required.

## Installation

```bash
git clone https://github.com/your-name/antigravity-project-merger.git
cd antigravity-project-merger
```

## Usage

### Preview changes

```bash
python3 merge_all_in_one.py migrate --dry-run
```

### Create backup

```bash
python3 merge_all_in_one.py backup
```

### Run migration

```bash
python3 merge_all_in_one.py migrate
```

### Run migration without prompts

```bash
python3 merge_all_in_one.py migrate --force
```

### Restore from backup

```bash
python3 merge_all_in_one.py restore
```

## Commands

```bash
python3 merge_all_in_one.py [backup | migrate | restore] [--dry-run] [--force]
```

| Command | Description |
|---|---|
| `backup` | Create a physical backup of Antigravity project and conversation data |
| `migrate` | Merge duplicate projects and migrate conversation references |
| `restore` | Restore data from the previous backup |

| Option | Description |
|---|---|
| `--dry-run` | Preview changes without modifying files |
| `--force` | Skip interactive confirmation prompts |

## Data Paths

```txt
~/.gemini/config/projects
~/.gemini/antigravity/agyhub_summaries_proto.pb
```

## Safety Notes

Close Antigravity before running this tool.

This tool modifies local Antigravity configuration and conversation metadata. Review the dry-run output carefully before applying changes.

## Disclaimer

This project is not affiliated with or endorsed by Antigravity, Google, or Gemini.

Use it at your own risk.

## License

MIT
