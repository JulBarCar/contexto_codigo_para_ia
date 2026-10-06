---
name: contexto
description: Use when exploring an unfamiliar repository, when asked to save tokens/context, or when a task mentions generating or reading contexto/ia_* context files. Wraps the `contexto` CLI, which packages a codebase (or a subset of it) into a token-efficient text file for LLMs.
---

# contexto — token-efficient codebase context

`contexto` builds a single text file from a repository so you can read a
codebase in one shot instead of exploring it file by file. It estimates
tokens, keeps the output under the model window, and exposes a machine
contract (`--json`) designed for agents.

Two commands cover 90% of the workflow: **survey first, then request files**.

## Machine contract

```bash
contexto . --json [flags]
```

- **stdout** = one JSON line (always the last line). Logs go to stderr.
- Add `--stdout` to get the generated content instead of a file: without
  `--json` stdout is the raw content; with `--json` the content is in the
  `content` field of the JSON line.
- Exit codes: `0` ok · `1` runtime error · `2` bad usage · `3` output larger
  than `--max-stdout` (file is kept; `output_path` is in the payload).
- Errors: `{"ok": false, "error": "...", "kind": "error|usage|limit"}`.

Main payload fields: `ok`, `mode`, `output_path`, `files`, `included`
(first 50 paths), `tokens`, `bytes`, `window_pct`, `warnings`, `dropped`,
`dropped_count`, `presupuesto`, `content` (with `--json --stdout`).

## Workflow

### 1. Survey the codebase (no source code, cheap)

```bash
contexto . --json --stdout --max-stdout 100000 \
  --co --objetivo "<task>" --sin-instrucciones
```

Read the JSON `content` field first. The `<file_index>` has one entry per file
with `path`, `lines`, `ext`, `tokens="~N"`, `symbols="..."` and detected
imports; the `<dependency_graph>` resolves internal files when possible. Pick
the minimum set of files you need from those fields instead of opening files
speculatively.

### 2. Request exactly those files (with source code)

```bash
contexto . --json --stdout --max-stdout 100000 \
  --objetivo "<task>" --archivos src/auth.py src/models --sin-instrucciones
```

`--archivos` takes files **and directories** (directories expand to their
included files, deduplicated). The XML payload ends with `</codebase>` (or
`</response_instructions>` when instructions are included).

### 3. If it does not fit

- `--presupuesto N` — trim the priority-ordered file list to ~N tokens.
  Files left out appear in `dropped`/`dropped_count`; at least one file is
  always included. Estimation is cheap (file size on disk, no re-read).
- Use `--presupuesto N` only when the first survey is too large. Very small
  budgets can remove dependency targets from the map, making the graph less
  useful.
- `--continua` — second round: omits `<context_metadata>`, `<task>` and
  `<file_index>` already sent in round 1. Only valid with
  `--objetivo` + `--archivos`.
- `--sin-instrucciones` — drops `<response_instructions>` when you already
  know the protocol (you are reading this skill).

### Whole repository

```bash
contexto . --json
```

Writes `contexto_codigo.txt` and returns `output_path`, `tokens` and
`window_pct` (use `warnings: ["window_exceeded"]` to know it is too big;
then prefer the two-step workflow above).

## Quick reference

| Flag | Purpose |
| --- | --- |
| `--co` | Context only: tree + dependency graph + file_index, no code |
| `--objetivo "..."` | Enables the AI-optimized XML format and names the output `ia_[slug]_*.txt` |
| `--archivos f1 dir2 ...` | Restrict output to these files/directories |
| `--presupuesto N` | Cap the output at ~N tokens (see `dropped` in JSON) |
| `--stdout` | Return content on stdout instead of writing a file |
| `--max-stdout N` | Token cap for `--stdout` (default 15000, `0` = unlimited) |
| `--continua` | Second round, skips metadata already sent |
| `--sin-instrucciones` | Omit `<response_instructions>` |
| `--preview` / `--stats` | List files / token estimate without writing anything |
| `--modelo NAME` | Token estimation model: `claude`, `gpt-4o`, `gemini`, `default`... |

Outputs land in `.codigo_completo/` (configurable via
`.codigo_config.json`, created with `contexto . --init`). If the `contexto`
command is not on PATH, run `python code_context.py` from the project root
or install with `setup_windows.bat` / `setup_linux.sh`.
