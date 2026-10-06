# Agent Guide

This repository contains `contexto`, a Python CLI that packages codebases into token-efficient context for AI agents.

## Project Map

- `code_context.py`: main entrypoint and orchestration.
- `modules/cli.py`: command-line argument parsing.
- `modules/config/`: default config and `.codigo_config.json` loader.
- `modules/filesystem/`: file collection, filtering and ordering.
- `modules/imports/`: import extraction and internal dependency graph.
- `modules/imports/strategies/`: language-specific import strategies.
- `modules/output/`: output writers, JSON/stdout handling, preview, Markdown and LaTeX.
- `modules/ai.py`: token estimation and objective slugs.
- `skills/contexto/SKILL.md`: opencode skill installed by setup scripts.
- `docs/OPENCODE.md`: integration guide for opencode.

## Common Commands

Compile key files:

```bash
python -m py_compile code_context.py modules/aliases/resolver.py modules/imports/core.py modules/output/writers.py
```

Generate an agent map from this repo:

```bash
python code_context.py . --json --stdout --max-stdout 100000 \
  --co --objetivo "understand this repository" --sin-instrucciones
```

Install on Windows after changes:

```bat
setup_windows.bat --no-pause
```

Install on Linux/macOS after changes:

```bash
bash setup_linux.sh
```

## Expected Agent Workflow

For an unfamiliar repository, use the installed CLI like this:

```bash
contexto . --json --stdout --max-stdout 100000 \
  --co --objetivo "<task>" --sin-instrucciones
```

Then request only selected files:

```bash
contexto . --json --stdout --max-stdout 100000 \
  --objetivo "<task>" --archivos path/to/file.py --sin-instrucciones
```

## Implementation Notes

- Keep the CLI dependency-free; use only the Python standard library.
- Preserve the JSON machine contract: stdout must contain one JSON object in `--json` mode.
- Logs should go to stderr in JSON mode.
- Prefer small, direct changes over broad rewrites.
- Do not commit generated `.codigo_completo/` outputs.
- When changing map output, verify both `<file_index>` and `<dependency_graph>`.

## Generated Files

The CLI writes generated context to `.codigo_completo/` by default. This directory is ignored by git and should not be treated as source.
