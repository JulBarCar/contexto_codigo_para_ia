"""
modules/imports/strategies/js_strategy.py
Extracción de importaciones para JS, TS, JSX, TSX, MJS y CJS mediante regex.
"""

import re
from pathlib import Path

from .base import ImportStrategy

# Marcador que se emite cuando se detecta un import() dinámico con template
# literal que empieza directamente con la variable, ej: import(`${locale}/x`).
# No hay ruta estática que resolver, pero sí hay una dependencia real.
# resolver_importacion debe ignorar este token (no intentar buscarlo en disco).
DYNAMIC_IMPORT_MARKER = "__dynamic__"


class JsStrategy(ImportStrategy):
    """
    Extrae importaciones de archivos JavaScript / TypeScript y sus variantes.

    Cubre:
      • import ... from 'x'              (estático, incluyendo multilínea)
      • export { ... } from 'x'          (re-export nombrado / default)
      • export * from 'x'                (re-export namespace)
      • import('x')                      (dinámico, string literal)
      • import(`./pre/${var}`)           (dinámico con prefijo estático)
      • import(`${var}/x`)              (dinámico sin prefijo → __dynamic__)
      • require('x') / require("x")     (CJS, incl. desestructuración)

    El método `preparar_cuerpo` es sobreescribible para que subclases
    (p.ej. VueStrategy, SvelteStrategy) puedan pre-procesar el texto
    antes del parsing.
    """

    EXTENSIONES: frozenset[str] = frozenset(
        {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}
    )

    # ── Patrones compilados a nivel de clase (se crean una sola vez) ──────────

    _PATRON_STRINGS = re.compile(
        r'(`[^`\\]*(?:\\.[^`\\]*)*`)'
        r'|("(?:[^"\\]|\\.)*")'
        r"|('(?:[^'\\]|\\.)*')",
        re.DOTALL,
    )
    _PATRON_STATIC = re.compile(
        r"""
        (?:
            \bimport\b
            (?:\s+type\b)?
            \s*
            (?:[\s\S]*?)?
            \bfrom\b
        |
            \bexport\b
            (?:\s+type\b)?
            \s*
            (?:\{[\s\S]*?\}|\*)
            (?:\s+as\s+\w+)?
            \s*
            \bfrom\b
        )
        \s*
        (?:['"]([^'"]+)['"])
        """,
        re.VERBOSE | re.DOTALL,
    )
    _PATRON_SIDE    = re.compile(r"""\bimport\s+['"]([^'"]+)['"]""")
    _PATRON_DYN_STR = re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)""")
    # Captura el prefijo estático antes del primer ${ en un template literal.
    # Casos:
    #   import(`./plugins/${name}`)  → group(1) = './plugins/'  → emitir prefijo
    #   import(`${locale}/messages`) → group(1) = ''            → emitir __dynamic__
    _PATRON_DYN_TPL = re.compile(r"""\bimport\s*\(\s*`([^`$]*)\$\{""")
    _PATRON_REQUIRE = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")
    _PATRON_STRLIT  = re.compile(r"__STRLIT_(\d+)__")

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        cuerpo = self.preparar_cuerpo(texto)
        cuerpo_safe = self._sanitizar(cuerpo)
        return self._extraer_especificadores(cuerpo_safe)

    # ── Hook para subclases ───────────────────────────────────────────────────

    def preparar_cuerpo(self, texto: str) -> str:
        """
        Transforma el texto antes de parsearlo.
        Por defecto devuelve el texto tal cual.
        Las subclases pueden sobrescribir este método para, por ejemplo,
        extraer solo el contenido de un bloque <script>.
        """
        return texto

    # ── Lógica privada ────────────────────────────────────────────────────────

    def _sanitizar(self, cuerpo: str) -> str:
        """
        Protege string literals, elimina comentarios y los restaura.
        Así los comentarios dentro de strings no interfieren con los patrones.
        """
        protegidos: list[str] = []

        def guardar(m: re.Match) -> str:
            idx = len(protegidos)
            protegidos.append(m.group(0))
            return f"__STRLIT_{idx}__"

        safe = self._PATRON_STRINGS.sub(guardar, cuerpo)
        safe = re.sub(r"/\*[\s\S]*?\*/", " ", safe)   # comentarios bloque
        safe = re.sub(r"//[^\n]*", "", safe)           # comentarios línea

        def restaurar(m: re.Match) -> str:
            return protegidos[int(m.group(1))]

        return self._PATRON_STRLIT.sub(restaurar, safe)

    def _extraer_especificadores(self, cuerpo: str) -> list[str]:
        """Aplica todos los patrones sobre el cuerpo ya sanitizado."""
        encontrados: list[str] = []

        # 1. import estático + re-exports (from '...')
        for m in self._PATRON_STATIC.finditer(cuerpo):
            if m.group(1):
                encontrados.append(m.group(1))

        # 2. import side-effect: import './reset.css'
        for m in self._PATRON_SIDE.finditer(cuerpo):
            encontrados.append(m.group(1))

        # 3. import() dinámico — string literal
        for m in self._PATRON_DYN_STR.finditer(cuerpo):
            encontrados.append(m.group(1))

        # 4. import() dinámico — template literal
        #    Con prefijo  → emitir el prefijo para búsqueda por disco
        #    Sin prefijo  → emitir DYNAMIC_IMPORT_MARKER (dependencia real
        #                   pero irresoluble estáticamente)
        for m in self._PATRON_DYN_TPL.finditer(cuerpo):
            prefijo = m.group(1)
            encontrados.append(prefijo if prefijo else DYNAMIC_IMPORT_MARKER)

        # 5. require('x') — CJS
        for m in self._PATRON_REQUIRE.finditer(cuerpo):
            encontrados.append(m.group(1))

        return encontrados