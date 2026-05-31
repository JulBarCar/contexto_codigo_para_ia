"""
modules/imports/strategies/php_strategy.py
Extracción de importaciones para archivos .php — nivel producción.

Mejoras respecto a la versión anterior:
  1. Expande `use` con llaves agrupadas (PHP 7+):
     "use Foo\\{Bar, Baz};" → ["Foo\\Bar", "Foo\\Baz"]
     "use function Foo\\{bar, baz};" → ["Foo\\bar", "Foo\\baz"]
  2. Lee composer.json para obtener el mapa de namespaces PSR-4 / PSR-0
     y resuelve los namespaces a rutas físicas de archivo:
     "App\\Models\\User" con PSR-4 "App\\" → "src/" → src/Models/User.php
  3. Detecta raíz del proyecto subiendo hasta encontrar composer.json.
  4. composer.json se carga una sola vez por instancia (cached_property).
  5. `require` / `include` con variables o concatenaciones de string se
     emiten como __dynamic__ (no resolubles estáticamente).

Cubre:
  • use Foo\\Bar\\Baz;                  (namespace import → resuelto PSR-4)
  • use Foo\\Bar\\Baz as Alias;         (con alias)
  • use function Foo\\bar;              (import de función)
  • use const Foo\\BAR;                 (import de constante)
  • use Foo\\{Bar, Baz};               (agrupado PHP 7+ → expandido)
  • require 'file.php';                 (require literal → emitido)
  • require_once 'file.php';            (require_once)
  • include 'file.php';                 (include)
  • include_once 'file.php';            (include_once)
  • require $var / require __DIR__.'x'; (dinámico → __dynamic__)
"""

import json
import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy

_DYNAMIC_MARKER = "__dynamic__"


class PhpStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".php", ".phtml", ".php5", ".php7", ".phps"})

    _PATRON_USE = re.compile(
        r"^\s*use\s+(?:function\s+|const\s+)?"
        r"([\w\\]+(?:\\\{[^}]*\})?)"
        r"(?:\s+as\s+\w+)?\s*;",
        re.MULTILINE,
    )
    # Require/include con string literal estático
    _PATRON_REQUIRE_STATIC = re.compile(
        r"""(?:require|require_once|include|include_once)\s*\(?\s*['"]([^'"]+)['"]\s*\)?;""",
        re.MULTILINE,
    )
    # Require/include con expresión dinámica (variable o concatenación)
    _PATRON_REQUIRE_DYNAMIC = re.compile(
        r"""(?:require|require_once|include|include_once)\s*\(?\s*(?!\s*['"])""",
        re.MULTILINE,
    )

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._raiz or self._detectar_raiz(archivo)

        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", texto)
        limpio = re.sub(r"//[^\n]*", "", limpio)
        limpio = re.sub(r"#[^\n]*", "", limpio)

        resultado: list[str] = []

        # use / use function / use const (con posible expansión de llaves)
        for m in self._PATRON_USE.finditer(limpio):
            raw = m.group(1)
            expandidos = self._expandir(raw)
            for ns in expandidos:
                if raiz is not None:
                    resultado.append(self._resolver_ns(ns, raiz))
                else:
                    resultado.append(ns)

        # require/include estáticos
        for m in self._PATRON_REQUIRE_STATIC.finditer(limpio):
            resultado.append(m.group(1))

        # require/include dinámicos → marcador
        for _ in self._PATRON_REQUIRE_DYNAMIC.finditer(limpio):
            resultado.append(_DYNAMIC_MARKER)

        return resultado

    # ── Expansión de use agrupados ────────────────────────────────────────────

    def _expandir(self, raw: str) -> list[str]:
        """
        Expande "Foo\\{Bar, Baz}" → ["Foo\\Bar", "Foo\\Baz"].
        Si no hay llaves, devuelve [raw].
        """
        if "{" not in raw:
            return [raw]

        idx      = raw.index("{")
        prefijo  = raw[:idx].rstrip("\\")
        interior = raw[idx + 1 : raw.rindex("}")].strip()

        return [
            f"{prefijo}\\{parte.strip()}" if prefijo else parte.strip()
            for parte in interior.split(",")
            if parte.strip()
        ]

    # ── Resolución PSR-4 ──────────────────────────────────────────────────────

    def _resolver_ns(self, ns: str, raiz: Path) -> str:
        """
        Resuelve un namespace PHP a su ruta física usando el mapa PSR-4
        leído de composer.json. Si no hay coincidencia, devuelve ns as-is.
        """
        psr4 = self._psr4_map(raiz)
        ns_normalizado = ns.replace("\\\\", "\\").lstrip("\\")

        for prefijo_ns, directorios in psr4.items():
            prefijo_ns = prefijo_ns.rstrip("\\") + "\\"
            if ns_normalizado.startswith(prefijo_ns):
                sufijo = ns_normalizado[len(prefijo_ns):]
                ruta_relativa = sufijo.replace("\\", "/")
                for directorio in directorios:
                    directorio = directorio.rstrip("/")
                    candidato = raiz / directorio / (ruta_relativa + ".php")
                    if candidato.exists():
                        try:
                            return candidato.relative_to(raiz).as_posix()
                        except ValueError:
                            return str(candidato).replace("\\", "/")

        return ns  # dep externa o namespace no registrado

    @cached_property
    def _cache_psr4(self) -> dict[Path, dict[str, list[str]]]:
        return {}

    def _psr4_map(self, raiz: Path) -> dict[str, list[str]]:
        """
        Carga el mapa PSR-4 (y PSR-0 como fallback) desde composer.json.
        Resultado cacheado por raíz.
        """
        if raiz in self._cache_psr4:
            return self._cache_psr4[raiz]

        mapa: dict[str, list[str]] = {}
        composer_json = raiz / "composer.json"

        if composer_json.exists():
            try:
                data = json.loads(composer_json.read_text(encoding="utf-8"))
                for seccion in ("autoload", "autoload-dev"):
                    for estandar in ("psr-4", "psr-0"):
                        for ns, dirs in (data.get(seccion, {}).get(estandar) or {}).items():
                            dirs_lista = [dirs] if isinstance(dirs, str) else list(dirs)
                            if ns in mapa:
                                mapa[ns].extend(dirs_lista)
                            else:
                                mapa[ns] = dirs_lista
            except Exception:
                pass

        self._cache_psr4[raiz] = mapa
        return mapa

    # ── Detección de raíz ─────────────────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar composer.json."""
        actual = archivo.parent
        for _ in range(20):
            if (actual / "composer.json").exists():
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None