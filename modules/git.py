"""
modules/git.py
Integración con git: archivos modificados y commits recientes.
"""

import subprocess
from pathlib import Path


def _fix_encoding(texto: str) -> str:
    """
    Corrige texto mal decodificado en Windows (latin-1 interpretado como UTF-8).
    Ej: 'rediseÃ±o' → 'rediseño'
    """
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texto


def obtener_archivos_modificados(raiz: Path) -> list[Path] | None:
    def run(cmd):
        r = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []

    check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=raiz, capture_output=True, text=True
    )
    if check.returncode != 0:
        print("[GIT]    No es un repositorio git — se omite el archivo de cambios.")
        return None

    orig_head = run(["git", "rev-parse", "--verify", "ORIG_HEAD"])
    if orig_head:
        archivos = run(["git", "diff", "--name-only", "--diff-filter=ACMR", "ORIG_HEAD", "HEAD"])
        origen   = "ORIG_HEAD → HEAD (último pull/merge)"
    else:
        staged   = run(["git", "diff", "--name-only", "--diff-filter=ACMR", "--cached"])
        unstaged = run(["git", "diff", "--name-only", "--diff-filter=ACMR"])
        archivos = list(dict.fromkeys(staged + unstaged))
        origen   = "working tree (cambios sin commitear)"

    if not archivos:
        print("[GIT]    Sin archivos modificados detectados.")
        return []

    print(f"[GIT]    {len(archivos)} archivo(s) modificado(s)  ({origen})")
    return [raiz / p for p in archivos if (raiz / p).exists()]


def obtener_ultimos_commits(raiz: Path, n: int = 5) -> list[str]:
    r = subprocess.run(
        ["git", "log", "--oneline", f"-{n}"],
        cwd=raiz, capture_output=True,
        encoding="utf-8", errors="replace"
    )
    if r.returncode != 0:
        return []
    lineas = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return [_fix_encoding(l) for l in lineas]