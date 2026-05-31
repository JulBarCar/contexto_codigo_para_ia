"""
modules/imports/strategies/python_strategy.py
Extracción de importaciones para archivos .py usando el AST de Python.
"""

import ast
from pathlib import Path

from .base import ImportStrategy


class PythonStrategy(ImportStrategy):
    """
    Extrae importaciones de archivos Python mediante análisis del AST.

    Comportamiento:
      - import foo           → devuelve 'foo'  (primer nivel del módulo)
      - from foo.bar import  → devuelve 'foo'  (primer nivel del módulo)
      - from . import x      → intenta resolver a ruta relativa real;
                               si no existe en disco, devuelve '.x'
      - from ..utils import  → intenta resolver; si no, devuelve '..utils'
    """

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix == ".py"

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        importaciones: list[str] = []

        try:
            tree = ast.parse(texto)
        except SyntaxError:
            return importaciones

        dir_actual = archivo.parent

        for nodo in ast.walk(tree):

            # ── import foo / import foo.bar ───────────────────────────────────
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    importaciones.append(alias.name.split(".")[0])

            # ── from [.] module import names ─────────────────────────────────
            elif isinstance(nodo, ast.ImportFrom):
                level  = nodo.level
                module = nodo.module

                # Importación absoluta
                if level == 0:
                    if module:
                        importaciones.append(module.split(".")[0])
                    continue

                # Importación relativa: subir `level - 1` directorios
                base = dir_actual
                for _ in range(level - 1):
                    base = base.parent

                # Caso: from . import nombre1, nombre2  (sin módulo explícito)
                if not module:
                    for alias in nodo.names:
                        sub = base / alias.name
                        resuelto = self._resolver_nombre_simple(
                            base, alias.name, dir_actual, level
                        )
                        importaciones.append(resuelto)
                    continue

                # Caso: from .sub.mod import ...
                subpath   = Path(*module.split("."))
                candidato = base / subpath
                ruta      = self._resolver_candidato(candidato)

                if ruta is not None:
                    try:
                        importaciones.append(
                            str(ruta.relative_to(dir_actual)).replace("\\", "/")
                        )
                    except ValueError:
                        importaciones.append(str(ruta).replace("\\", "/"))
                else:
                    importaciones.append("." * level + module)

        return importaciones

    # ── helpers privados ──────────────────────────────────────────────────────

    def _resolver_nombre_simple(
        self,
        base: Path,
        nombre: str,
        dir_actual: Path,
        level: int,
    ) -> str:
        """Resuelve 'from . import nombre' a ruta o especificador con puntos."""
        archivo_py = base / f"{nombre}.py"
        paquete    = base / nombre / "__init__.py"

        if archivo_py.exists():
            try:
                return str(archivo_py.relative_to(dir_actual)).replace("\\", "/")
            except ValueError:
                return f"{'.' * level}{nombre}"

        if paquete.exists():
            try:
                return str((base / nombre).relative_to(dir_actual)).replace("\\", "/")
            except ValueError:
                return f"{'.' * level}{nombre}"

        return f"{'.' * level}{nombre}"

    def _resolver_candidato(self, candidato: Path) -> Path | None:
        """Devuelve la ruta real (.py o paquete) o None si no existe."""
        como_modulo  = Path(str(candidato) + ".py")
        como_paquete = candidato / "__init__.py"

        if como_modulo.exists():
            return como_modulo
        if como_paquete.exists():
            return candidato
        return None