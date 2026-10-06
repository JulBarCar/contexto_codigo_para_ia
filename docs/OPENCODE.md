# Opencode Integration

This project ships a global CLI, `contexto`, and an opencode skill, `contexto`, designed to work together.

## Goal

After installation, an opencode agent can explore any repository with a cheap structural map before reading source code. This reduces token usage and makes file selection more deliberate.

## Install

From this repository root:

Windows:

```bat
setup_windows.bat
```

Linux/macOS:

```bash
bash setup_linux.sh
```

The installers copy:

- `code_context.py` and `modules/` into the CLI install directory.
- `skills/contexto/SKILL.md` into `~/.config/opencode/skills/contexto/SKILL.md`.

## Verify

```bash
contexto --ayuda
```

Then verify the agent-oriented contract:

```bash
contexto . --agent-map "understand this repository"
```

Expected behavior:

- stdout is one JSON object.
- `ok` is `true`.
- `mode` is `mapa_ia`.
- `content` contains XML-like context.
- `<file_index>` is present.
- `<recommended_files>` is present when useful files are detected.
- `<dependency_graph>` is present.
- JSON includes token-saving metrics when available.

## Recommended Agent Workflow

Survey first, no source code:

```bash
contexto . --agent-map "<task>"
```

Request only needed files:

```bash
contexto . --json --stdout --max-stdout 100000 \
  --objetivo "<task>" --archivos path/to/file.py path/to/dir --sin-instrucciones
```

Continue without repeated metadata:

```bash
contexto . --json --stdout --max-stdout 100000 \
  --objetivo "<task>" --archivos path/to/file.py --continua --sin-instrucciones
```

## Skill Behavior

The skill tells opencode agents to:

- Use the structural map before reading source code.
- Prefer `--json --stdout` for machine consumption.
- Inspect `content` from the JSON payload.
- Pick files from `path`, `role`, `symbols`, `tokens`, `imports`, `depends_on`, `used_by`, `<recommended_files>` and `<dependency_graph>`.
- Use `--archivos` for precise follow-up context.

If `--agent-map` is unavailable, use the equivalent long form:

```bash
contexto . --json --stdout --max-stdout 100000 \
  --co --objetivo "<task>" --sin-instrucciones
```

## Diagnostics

Check the installed version:

```bash
contexto --version
```

Run installation diagnostics:

```bash
contexto doctor
contexto doctor --json
```

## When To Use A Budget

Use `--presupuesto N` only when the first survey is too large for stdout or the model context window.

Avoid very small budgets in the first survey. They can remove files that dependency targets point to, making the graph less useful.

## Installing The Skill Manually

Windows:

```bat
mkdir "%USERPROFILE%\.config\opencode\skills\contexto"
copy /Y skills\contexto\SKILL.md "%USERPROFILE%\.config\opencode\skills\contexto\SKILL.md"
```

Linux/macOS:

```bash
mkdir -p ~/.config/opencode/skills/contexto
cp skills/contexto/SKILL.md ~/.config/opencode/skills/contexto/SKILL.md
```

## Updating An Existing Installation

Run the installer again after changing this repo.

Windows non-interactive:

```bat
setup_windows.bat --no-pause
```

Linux/macOS:

```bash
bash setup_linux.sh
```

## Troubleshooting

If `contexto` is not found after installation on Windows, close and reopen the terminal.

If opencode does not see the skill, confirm this file exists:

```text
~/.config/opencode/skills/contexto/SKILL.md
```

If the global command appears stale, run:

```bash
where contexto
```

or on Linux/macOS:

```bash
which contexto
```

Then reinstall from the latest checkout.
