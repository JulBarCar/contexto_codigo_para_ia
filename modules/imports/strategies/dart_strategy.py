"""
modules/imports/strategies/dart_strategy.py
Extracción de importaciones para archivos .dart (Dart / Flutter) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Clasifica cada import en tres categorías:
       - dart:*      → SDK core, se emiten como están (no existen en disco)
       - package:*   → dependencias pub, se emiten como están
       - relativo    → path relativo, se resuelve a ruta absoluta normalizada
  2. Los paths relativos se resuelven a ruta relativa respecto al archivo
     actual, tal como hace resolver_importacion con otros lenguajes.
  3. 'part of' se ignora (es la declaración de pertenencia, no una dep).
  4. Elimina string multilínea (''' y \"\"\") antes de parsear para evitar
     falsos positivos en strings que contienen import como texto.

Cubre:
  • import 'package:flutter/material.dart';     (paquete pub → emitido as-is)
  • import 'dart:core';                         (SDK → emitido as-is)
  • import 'relative/path.dart';               (relativo → resuelto en disco)
  • import '...' as alias;                     (alias, ignorado para el path)
  • import '...' show Foo, Bar;                (show, ignorado para el path)
  • import '...' hide Baz;                     (hide, ignorado para el path)
  • export 'package:foo/foo.dart';             (re-export)
  • part 'file.dart';                          (part directive → resuelto)
  • part of '...';                             (ignorado)
"""

import re
from pathlib import Path

from .base import ImportStrategy


class DartStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".dart"})

    # Eliminar strings multilínea antes de parsear
    _PATRON_MULTILINE_STR = re.compile(
        r"(?:'{3}[\s\S]*?'{3}|\"{3}[\s\S]*?\"{3})",
        re.DOTALL,
    )
    _PATRON_IMPORT = re.compile(
        r"""^\s*(?:import|export)\s+['"]([^'"]+)['"]\s*"""
        r"""(?:as\s+\w+\s*)?(?:show\s+[\w\s,]+)?(?:hide\s+[\w\s,]+)?\s*;""",
        re.MULTILINE,
    )
    _PATRON_PART = re.compile(
        r"""^\s*part\s+(?!of\s)['"]([^'"]+)['"]\s*;""",
        re.MULTILINE,
    )

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        limpio = self._PATRON_MULTILINE_STR.sub(" ", texto)
        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", limpio)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        resultado: list[str] = []
        for m in self._PATRON_IMPORT.finditer(limpio):
            resultado.append(self._resolver(m.group(1), archivo))
        for m in self._PATRON_PART.finditer(limpio):
            resultado.append(self._resolver(m.group(1), archivo))
        return resultado

    # ── Resolución ────────────────────────────────────────────────────────────

    def _resolver(self, imp: str, archivo: Path) -> str:
        """
        - dart:* y package:* → devueltos tal cual (no son rutas de disco)
        - paths relativos     → normalizados a ruta relativa desde el archivo
        """
        if imp.startswith("dart:") or imp.startswith("package:"):
            return imp

        # Path relativo: resolver desde el directorio del archivo
        try:
            ruta_abs = (archivo.parent / imp).resolve()
            # Intentar hacer relativa al directorio del propio archivo
            # (resolver_importacion usará el índice global para el lookup)
            return str(ruta_abs.relative_to(archivo.parent.resolve())).replace("\\", "/")
        except (ValueError, OSError):
            return imp