"""
modules/imports/strategies/shell_strategy.py
Extracción de dependencias para archivos Shell / Bash — nivel producción.

Mejoras respecto a la versión anterior:
  1. Distingue `source` / `.` estático (ruta literal) de dinámico
     (ruta con expansión de variable o sustitución de comando):
       source ./lib.sh          → emitido y resuelto en disco
       source "$DIR/lib.sh"     → marcado como __dynamic__
       source "$(get_path)"     → marcado como __dynamic__
  2. Resuelve rutas de source literales a rutas físicas reales
     relativas al archivo (antes solo se emitía el string tal cual).
  3. Detecta `PATH` y herramientas externas con mayor fidelidad:
       • command -v foo         → "foo"
       • which foo              → "foo"
       • type -P foo            → "foo"  (nueva)
       • hash foo               → "foo"  (nueva)
  4. Emite el runtime del shebang con mayor granularidad:
       #!/usr/bin/env bash      → "bash"
       #!/bin/sh                → "sh"
       #!/usr/bin/python3       → "python3"
  5. Detecta llamadas a scripts locales (./script.sh, ../lib/util.sh)
     como dependencias aunque no usen `source`.

Nota: Shell no tiene un sistema de imports formal. Se emiten las rutas
de archivos incluidos vía `source` / `.` y las herramientas verificadas
con `command -v` / `which` / `type -P` / `hash`, representando deps reales.
"""

import re
from pathlib import Path

from .base import ImportStrategy

_DYNAMIC_MARKER = "__dynamic__"


class ShellStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({
        ".sh", ".bash", ".zsh", ".fish",
        ".env",
    })

    # source / . seguido de una ruta literal (sin $ ni `)
    _PATRON_SOURCE_STATIC = re.compile(
        r"""^\s*(?:source|\.)\s+(?!["']*\$|["']*`)(['"]?)([^$`\s#'";&|]+)\1""",
        re.MULTILINE,
    )
    # source / . con expresión dinámica ($VAR, `cmd`, $(cmd))
    _PATRON_SOURCE_DYNAMIC = re.compile(
        r"""^\s*(?:source|\.)\s+['"]?(?:\$|\`)""",
        re.MULTILINE,
    )
    # Llamadas directas a scripts locales: ./script.sh ../lib/util.sh
    _PATRON_LOCAL_SCRIPT = re.compile(
        r"""(?:^|[;|&\s])(\.[./\w-]*\.sh)\b""",
        re.MULTILINE,
    )
    # Verificación de herramientas externas
    _PATRON_COMMAND_V = re.compile(r"""\bcommand\s+-v\s+([\w.-]+)""")
    _PATRON_WHICH     = re.compile(r"""\bwhich\s+([\w.-]+)""")
    _PATRON_TYPE_P    = re.compile(r"""\btype\s+-[aP]+\s+([\w.-]+)""")
    _PATRON_HASH      = re.compile(r"""\bhash\s+([\w.-]+)""")
    # Shebang: extrae el intérprete final (env bash → bash; /bin/sh → sh)
    _PATRON_SHEBANG   = re.compile(
        r"""^#!\s*(?:/usr/bin/env\s+)?(?:[\w/.-]*/)?(\w[\w.-]*)"""
    )

    def soporta(self, archivo: Path) -> bool:
        return (
            archivo.suffix in self.EXTENSIONES
            or archivo.name in {
                ".bashrc", ".zshrc", ".profile", ".bash_profile",
                "Makefile", "makefile",
            }
        )

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        # Eliminar solo comentarios de línea completa
        limpio = re.sub(r"^\s*#[^\n]*", "", texto, flags=re.MULTILINE)

        resultado: list[str] = []

        # Shebang (primera línea del texto original, antes de limpiar)
        m_shebang = self._PATRON_SHEBANG.match(texto)
        if m_shebang:
            resultado.append(m_shebang.group(1))

        # source / . estático → intentar resolver a ruta física
        for m in self._PATRON_SOURCE_STATIC.finditer(limpio):
            ruta = m.group(2).strip()
            if ruta:
                resultado.append(self._resolver(ruta, archivo))

        # source / . dinámico → marcador
        for _ in self._PATRON_SOURCE_DYNAMIC.finditer(limpio):
            resultado.append(_DYNAMIC_MARKER)

        # Scripts locales invocados directamente (./script.sh)
        for m in self._PATRON_LOCAL_SCRIPT.finditer(limpio):
            ruta = m.group(1).strip()
            resultado.append(self._resolver(ruta, archivo))

        # Herramientas externas
        for patron in (
            self._PATRON_COMMAND_V,
            self._PATRON_WHICH,
            self._PATRON_TYPE_P,
            self._PATRON_HASH,
        ):
            for m in patron.finditer(limpio):
                resultado.append(m.group(1))

        return resultado

    # ── Resolución de rutas de source ─────────────────────────────────────────

    def _resolver(self, ruta: str, archivo: Path) -> str:
        """
        Intenta resolver la ruta de source / script relativa al archivo.
        Si existe en disco, devuelve la ruta relativa normalizada.
        """
        dir_actual = archivo.parent
        candidato  = (dir_actual / ruta).resolve()
        if candidato.exists():
            try:
                return str(candidato.relative_to(dir_actual.resolve())).replace("\\", "/")
            except ValueError:
                return str(candidato).replace("\\", "/")
        return ruta