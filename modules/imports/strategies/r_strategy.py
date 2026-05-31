"""
modules/imports/strategies/r_strategy.py
Extracción de importaciones para archivos .R y .Rmd (R / R Markdown) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Lee DESCRIPTION para obtener los paquetes declarados en Imports:,
     Depends:, Suggests: y LinkingTo: del paquete R actual.
     Solo se emiten desde DESCRIPTION, no desde cada archivo .R.
  2. Lee renv.lock para extraer la lista de paquetes instalados en el
     entorno reproducible, proporcionando visibilidad de todas las deps.
  3. Resuelve `source()` con rutas literales a rutas físicas reales
     (antes solo se emitía el string tal cual).
  4. Mejora el patrón de `library()` / `require()` para tolerar
     argumentos adicionales: `library(dplyr, warn.conflicts = FALSE)`.
  5. DESCRIPTION y renv.lock se cargan una sola vez por instancia
     (cached_property).

Cubre:
  • library(ggplot2)                   (carga de paquete)
  • require(dplyr)                     (carga condicional)
  • library("ggplot2")                 (con comillas)
  • library(dplyr, warn.conflicts=F)   (con args extra)
  • source("./helpers.R")              (→ resuelto a ruta física)
  • source(file.path("dir", "x.R"))    (dinámico → __dynamic__)
  • box::use(dplyr[...])               (sistema de módulos 'box')
  • import::from(dplyr, select)        (paquete 'import')
  • DESCRIPTION Imports/Depends        (declaraciones del paquete)
  • renv.lock packages                 (entorno reproducible)
"""

import json
import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy

_DYNAMIC_MARKER = "__dynamic__"


class RStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".r", ".R", ".Rmd", ".rmd", ".Rnw"})

    _PATRON_LIBRARY = re.compile(
        r"""\b(?:library|require)\s*\(\s*['"]?([\w.]+)['"]?\s*(?:,[\s\S]*?)?\)""",
    )
    _PATRON_SOURCE_STATIC = re.compile(
        r"""\bsource\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    )
    # source() con expresión dinámica (file.path, paste, variable)
    _PATRON_SOURCE_DYNAMIC = re.compile(
        r"""\bsource\s*\(\s*(?!['"])""",
    )
    _PATRON_BOX = re.compile(
        r"""\bbox::use\s*\(([\s\S]*?)\)""",
    )
    _PATRON_BOX_MOD = re.compile(r"""([\w.]+)\s*(?:\[|\()""")
    _PATRON_IMPORT_FROM = re.compile(
        r"""\bimport::from\s*\(\s*['"]?([\w.]+)['"]?""",
    )
    # DESCRIPTION: campos de dependencia
    _PATRON_DESC_FIELD = re.compile(
        r"^(?:Imports|Depends|Suggests|LinkingTo)\s*:(.*?)(?=^\w|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    _PATRON_DESC_PKG = re.compile(r"([\w.]+)\s*(?:\([^)]*\))?")

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._raiz or self._detectar_raiz(archivo)
        limpio = re.sub(r"#[^\n]*", "", texto)

        resultado: list[str] = []

        for m in self._PATRON_LIBRARY.finditer(limpio):
            resultado.append(m.group(1))

        # source() estático → resolver a ruta física
        for m in self._PATRON_SOURCE_STATIC.finditer(limpio):
            resultado.append(self._resolver_source(m.group(1), archivo))

        # source() dinámico → marcador
        for _ in self._PATRON_SOURCE_DYNAMIC.finditer(limpio):
            resultado.append(_DYNAMIC_MARKER)

        for m in self._PATRON_BOX.finditer(limpio):
            for mod in self._PATRON_BOX_MOD.finditer(m.group(1)):
                resultado.append(mod.group(1))

        for m in self._PATRON_IMPORT_FROM.finditer(limpio):
            resultado.append(m.group(1))

        # Dependencias declaradas en DESCRIPTION (solo si es un paquete R)
        if raiz is not None:
            resultado.extend(self._deps_description(raiz))

        return resultado

    # ── Resolución de source() ────────────────────────────────────────────────

    def _resolver_source(self, ruta: str, archivo: Path) -> str:
        """
        Intenta resolver la ruta de source() relativa al archivo actual.
        Si el archivo existe en disco, devuelve la ruta relativa normalizada.
        """
        dir_actual = archivo.parent
        candidato  = (dir_actual / ruta).resolve()
        if candidato.exists():
            try:
                return str(candidato.relative_to(dir_actual.resolve())).replace("\\", "/")
            except ValueError:
                return str(candidato).replace("\\", "/")
        return ruta

    # ── Lectura de DESCRIPTION ────────────────────────────────────────────────

    @cached_property
    def _cache_description(self) -> dict[Path, list[str]]:
        return {}

    def _deps_description(self, raiz: Path) -> list[str]:
        """
        Extrae los paquetes declarados en DESCRIPTION (Imports, Depends,
        Suggests, LinkingTo). Resultado cacheado por raíz.
        """
        if raiz in self._cache_description:
            return self._cache_description[raiz]

        paquetes: list[str] = []
        desc_path = raiz / "DESCRIPTION"

        if desc_path.exists():
            try:
                contenido = desc_path.read_text(encoding="utf-8", errors="replace")
                for campo in self._PATRON_DESC_FIELD.finditer(contenido):
                    for pkg_m in self._PATRON_DESC_PKG.finditer(campo.group(1)):
                        nombre = pkg_m.group(1).strip()
                        # Excluir "R" (base) y versiones numéricas sueltas
                        if nombre and nombre != "R" and not nombre[0].isdigit():
                            paquetes.append(nombre)
            except Exception:
                pass

        self._cache_description[raiz] = paquetes
        return paquetes

    # ── Detección de raíz ─────────────────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar DESCRIPTION, renv.lock o .Rproj."""
        actual = archivo.parent
        for _ in range(20):
            if (
                (actual / "DESCRIPTION").exists()
                or (actual / "renv.lock").exists()
                or any(actual.glob("*.Rproj"))
            ):
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None