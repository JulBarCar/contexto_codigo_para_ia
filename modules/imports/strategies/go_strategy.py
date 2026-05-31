"""
modules/imports/strategies/go_strategy.py
Extracción de importaciones para archivos .go — nivel producción.

Mejoras respecto a la versión anterior:
  1. Lee go.mod para conocer el module path del proyecto y distinguir
     imports internos (misma raíz de módulo) de externos (stdlib, deps).
  2. Emite el path completo de cada import, no solo la raíz.
  3. Resuelve imports internos a rutas de archivo relativas reales en disco
     (busca el directorio y, dentro, el primer .go que no sea _test.go).
  4. go.mod se carga una sola vez por instancia (cached_property).

Cubre:
  • import "fmt"                       (import simple)
  • import alias "pkg/path"            (import con alias)
  • import _ "pkg/path"               (import side-effect)
  • import . "pkg/path"               (import dot)
  • import ( ... )                     (bloque multilínea)
  • módulos internos                   → resueltos a ruta relativa en disco
  • módulos externos / stdlib          → emitidos como path completo
"""

import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy


class GoStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".go"})

    _PATRON_SIMPLE = re.compile(
        r"""^\s*import\s+(?:[\w_.]+\s+)?["']([^"']+)["']""",
        re.MULTILINE,
    )
    _PATRON_BLOQUE = re.compile(r"import\s*\(([\s\S]*?)\)", re.MULTILINE)
    _PATRON_ENTRADA = re.compile(r"""(?:[\w_.]+\s+)?["']([^"']+)["']""")
    _PATRON_MODULE  = re.compile(r"^module\s+([\S]+)", re.MULTILINE)

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        # Detectar raíz desde el archivo si no se proporcionó
        raiz = self._raiz or self._detectar_raiz(archivo)

        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", texto)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        paths: list[str] = []
        bloques: set[tuple[int, int]] = set()

        for bloque in self._PATRON_BLOQUE.finditer(limpio):
            bloques.add((bloque.start(), bloque.end()))
            for e in self._PATRON_ENTRADA.finditer(bloque.group(1)):
                paths.append(e.group(1))

        for m in self._PATRON_SIMPLE.finditer(limpio):
            if not any(s <= m.start() <= e for s, e in bloques):
                paths.append(m.group(1))

        if raiz is None:
            return paths

        modulo = self._modulo(raiz)
        resultado: list[str] = []
        for p in paths:
            resuelto = self._resolver(p, raiz, modulo, archivo)
            resultado.append(resuelto)
        return resultado

    # ── Resolución ────────────────────────────────────────────────────────────

    def _resolver(
        self,
        imp: str,
        raiz: Path,
        modulo: str | None,
        archivo: Path,
    ) -> str:
        """
        Si el import pertenece al módulo del proyecto, intenta resolverlo
        a una ruta relativa real dentro del proyecto.
        Si no, devuelve el path completo tal cual (stdlib / dep externa).
        """
        if modulo and imp.startswith(modulo + "/"):
            sufijo = imp[len(modulo) + 1:]          # "internal/auth"
            dir_pkg = raiz / Path(*sufijo.split("/"))
            if dir_pkg.is_dir():
                # Buscar el primer .go del paquete que no sea test
                for go_file in sorted(dir_pkg.glob("*.go")):
                    if not go_file.name.endswith("_test.go"):
                        try:
                            return go_file.relative_to(raiz).as_posix()
                        except ValueError:
                            return go_file.as_posix()
                # El directorio existe pero solo tiene test files → emitir dir
                try:
                    return dir_pkg.relative_to(raiz).as_posix()
                except ValueError:
                    pass
        return imp

    # ── go.mod (cargado una vez por instancia) ────────────────────────────────

    @cached_property
    def _cache_modulos(self) -> dict[Path, str | None]:
        return {}

    def _modulo(self, raiz: Path) -> str | None:
        if raiz in self._cache_modulos:
            return self._cache_modulos[raiz]
        gomod = raiz / "go.mod"
        resultado: str | None = None
        if gomod.exists():
            try:
                contenido = gomod.read_text(encoding="utf-8", errors="replace")
                m = self._PATRON_MODULE.search(contenido)
                if m:
                    resultado = m.group(1).strip()
            except Exception:
                pass
        self._cache_modulos[raiz] = resultado
        return resultado

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube por el árbol hasta encontrar go.mod."""
        actual = archivo.parent
        for _ in range(20):
            if (actual / "go.mod").exists():
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None