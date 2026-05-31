"""
modules/imports/strategies/ruby_strategy.py
Extracción de importaciones para archivos .rb (Ruby) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Lee Gemfile para obtener la lista de gems declaradas y las emite
     como dependencias del proyecto (útil para saber qué gems usa el
     proyecto aunque no haya un require explícito en el archivo actual).
     Solo se emiten desde Gemfile, no se mezclan en cada archivo .rb.
  2. Resuelve `require_relative` a rutas físicas reales en disco
     (antes solo se emitía el string tal cual).
  3. Detecta `bundler/require` / `Bundler.require` como marcador de
     que todas las gems del Gemfile son dependencias del archivo.
  4. Normaliza rutas de `require` con extensión `.rb` explícita:
     "require 'foo/bar.rb'" → "foo/bar.rb" (sin cambio; ya es resoluble).
  5. Gemfile se parsea una sola vez por instancia (cached_property).

Cubre:
  • require 'foo'                      (gem o stdlib → emitido as-is)
  • require_relative 'foo/bar'         (relativo → resuelto a ruta física)
  • require "foo"                      (comillas dobles → igual)
  • autoload :Foo, 'foo/bar'           (autoload → ruta emitida)
  • include Foo::Bar                   (mixin → módulo emitido)
  • prepend Foo::Bar                   (mixin prepend)
  • extend Foo::Bar                    (mixin extend)
  • require 'bundler/setup' /
    Bundler.require(...)               (bundler → marcador especial)
"""

import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy

_BUNDLER_MARKER = "__bundler_require__"


class RubyStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".rb", ".rake", ".gemspec", ".ru"})

    _PATRON_REQUIRE = re.compile(
        r"""^\s*require\s+['"]([^'"]+)['"]\s*$""",
        re.MULTILINE,
    )
    _PATRON_REQUIRE_RELATIVE = re.compile(
        r"""^\s*require_relative\s+['"]([^'"]+)['"]\s*$""",
        re.MULTILINE,
    )
    _PATRON_AUTOLOAD = re.compile(
        r"""^\s*autoload\s+:\w+\s*,\s*['"]([^'"]+)['"]\s*$""",
        re.MULTILINE,
    )
    _PATRON_MIXIN = re.compile(
        r"""^\s*(?:include|prepend|extend)\s+([\w:]+)""",
        re.MULTILINE,
    )
    _PATRON_BUNDLER = re.compile(
        r"""(?:require\s+['"]bundler(?:/setup|/require)?['"]|Bundler\.require)""",
    )
    # Parseo simplificado de Gemfile: gem 'nombre', ...
    _PATRON_GEMFILE_GEM = re.compile(
        r"""^\s*gem\s+['"]([^'"]+)['"]""",
        re.MULTILINE,
    )

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._raiz or self._detectar_raiz(archivo)
        limpio = re.sub(r"#[^\n]*", "", texto)

        resultado: list[str] = []

        # require estándar (gem / stdlib / ruta con extensión)
        for m in self._PATRON_REQUIRE.finditer(limpio):
            resultado.append(m.group(1))

        # require_relative → resolver a ruta física
        for m in self._PATRON_REQUIRE_RELATIVE.finditer(limpio):
            resultado.append(self._resolver_relativo(m.group(1), archivo))

        # autoload
        for m in self._PATRON_AUTOLOAD.finditer(limpio):
            resultado.append(m.group(1))

        # mixins
        for m in self._PATRON_MIXIN.finditer(limpio):
            resultado.append(m.group(1))

        # bundler/require → emitir marcador + todas las gems del Gemfile
        if self._PATRON_BUNDLER.search(limpio):
            resultado.append(_BUNDLER_MARKER)
            if raiz is not None:
                resultado.extend(self._gems_gemfile(raiz))

        return resultado

    # ── Resolución de require_relative ───────────────────────────────────────

    def _resolver_relativo(self, ruta: str, archivo: Path) -> str:
        """
        Resuelve require_relative 'foo/bar' a la ruta física relativa
        al directorio del archivo actual.
        Prueba con y sin extensión .rb.
        """
        dir_actual = archivo.parent
        candidatos = [
            dir_actual / ruta,
            dir_actual / (ruta + ".rb"),
        ]
        for candidato in candidatos:
            if candidato.exists():
                try:
                    return str(candidato.relative_to(dir_actual)).replace("\\", "/")
                except ValueError:
                    return str(candidato).replace("\\", "/")
        # No encontrado en disco — devolver la ruta tal como fue escrita
        return ruta if ruta.endswith(".rb") else ruta + ".rb"

    # ── Lectura de Gemfile ────────────────────────────────────────────────────

    @cached_property
    def _cache_gems(self) -> dict[Path, list[str]]:
        return {}

    def _gems_gemfile(self, raiz: Path) -> list[str]:
        """
        Devuelve la lista de gems declaradas en el Gemfile del proyecto.
        Resultado cacheado por raíz.
        """
        if raiz in self._cache_gems:
            return self._cache_gems[raiz]

        gems: list[str] = []
        gemfile = raiz / "Gemfile"
        if gemfile.exists():
            try:
                contenido = gemfile.read_text(encoding="utf-8", errors="replace")
                # Eliminar comentarios antes de parsear
                contenido = re.sub(r"#[^\n]*", "", contenido)
                for m in self._PATRON_GEMFILE_GEM.finditer(contenido):
                    gems.append(m.group(1))
            except Exception:
                pass

        self._cache_gems[raiz] = gems
        return gems

    # ── Detección de raíz ─────────────────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar Gemfile, Rakefile o .ruby-version."""
        marcadores = {"Gemfile", "Rakefile", ".ruby-version", "config.ru"}
        actual = archivo.parent
        for _ in range(20):
            if any((actual / m).exists() for m in marcadores):
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None