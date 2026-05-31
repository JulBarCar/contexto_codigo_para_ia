"""
modules/imports/strategies/c_strategy.py
Extracción de importaciones para archivos C y C++ — nivel producción v2.

Mejoras v2 respecto a v1:
  1. Lee CMakeLists.txt para extraer include_directories() y
     target_include_directories() — el conjunto real de rutas de búsqueda
     del proyecto en lugar de la lista hardcodeada.
     Resuelve las variables CMake más comunes:
       ${CMAKE_SOURCE_DIR}, ${CMAKE_CURRENT_SOURCE_DIR}, ${PROJECT_SOURCE_DIR}.
     Escanea la raíz y todos los subdirectorios de primer nivel.
  2. Parsea Makefile / makefile / GNUmakefile para flags
     -I / -isystem / -iquote, incluyendo sintaxis con y sin espacio.
  3. Detecta #include_next (extensión GCC/Clang) y lo trata igual que
     #include (mismo semántica de búsqueda para el grafo).
  4. Detecta __has_include(<hdr>) y __has_include("hdr") como include
     condicional → se emite con sufijo __conditional__.
  5. Soporte de extensiones C++20 (.ixx, .cppm para named modules).
  6. Los directorios de include se cargan una sola vez por instancia
     (cached_property sobre la raíz del proyecto).
"""

import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy

_DYNAMIC_MARKER     = "__dynamic__"
_CONDITIONAL_SUFFIX = "__conditional__"


class CStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({
        ".c", ".h",
        ".cpp", ".cc", ".cxx", ".c++",
        ".hpp", ".hh", ".hxx", ".h++",
        ".m", ".mm",            # Objective-C / Objective-C++
        ".cu", ".cuh",          # CUDA
        ".ixx", ".cppm",        # C++20 named modules
    })

    # Fallback cuando no hay CMakeLists.txt ni Makefile
    _INCLUDE_DIRS_FALLBACK: tuple[str, ...] = (
        "",
        "include", "inc", "src", "lib",
        "third_party", "vendor", "external",
    )

    # Keywords de CMake que no son rutas
    _CMAKE_KEYWORDS: frozenset[str] = frozenset({
        "PRIVATE", "PUBLIC", "INTERFACE", "BEFORE", "AFTER",
        "SYSTEM", "target", "IMPORTED", "IMPORTED_LOCATION",
    })

    # ── Regexes compilados ────────────────────────────────────────────────────

    _PATRON_INCLUDE_SYSTEM = re.compile(
        r"""^\s*#\s*include(?:_next)?\s*<([^>]+)>""",
        re.MULTILINE,
    )
    _PATRON_INCLUDE_LOCAL = re.compile(
        r'^\s*#\s*include(?:_next)?\s*"([^"]+)"',
        re.MULTILINE,
    )
    # C++20 import: import <module>; / import "header"; / import module.name;
    _PATRON_IMPORT_CPP20 = re.compile(
        r"""^\s*import\s+[<"']?([^;"'\s>]+)[>"']?\s*;""",
        re.MULTILINE,
    )
    # Include dinámico via macro: #include MACRO_NAME (no es literal)
    _PATRON_INCLUDE_DYNAMIC = re.compile(
        r"""^\s*#\s*include(?:_next)?\s+(?!["'<])(\w+)""",
        re.MULTILINE,
    )
    # __has_include(<hdr>) o __has_include("hdr") — siempre condicional
    _PATRON_HAS_INCLUDE = re.compile(
        r"""__has_include\s*\(\s*(?:<([^>]+)>|"([^"]+)")\s*\)""",
    )
    # CMake: captura todos los argumentos de include_directories(...)
    # y target_include_directories(target PRIVATE ...) en una sola pasada.
    _PATRON_CMAKE_INCDIRS = re.compile(
        r"""(?:include_directories|target_include_directories)\s*\(([^)]*)\)""",
        re.IGNORECASE | re.DOTALL,
    )
    # Makefile: -I<path> / -I <path> / -isystem <path> / -iquote <path>
    # Admite comillas y rutas con espacios escapados.
    _PATRON_MAKEFILE_I = re.compile(
        r"""-(?:I|isystem|iquote)\s*['"]?([^\s\\'"\n]+)['"]?""",
    )
    # Bloques condicionales del preprocesador
    _PATRON_COND_OPEN  = re.compile(r"""^\s*#\s*(?:if|ifdef|ifndef)\b""", re.MULTILINE)
    _PATRON_COND_CLOSE = re.compile(r"""^\s*#\s*endif\b""", re.MULTILINE)

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._raiz or self._detectar_raiz(archivo)

        # Eliminar comentarios preservando directivas de preprocesador
        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", texto)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        resultado: list[str]   = []
        condicionales          = self._rangos_condicionales(limpio)
        include_dirs           = self._include_dirs(raiz)

        # 1. Includes de sistema < >
        for m in self._PATRON_INCLUDE_SYSTEM.finditer(limpio):
            entrada = m.group(1)
            if self._es_condicional(m.start(), condicionales):
                entrada += _CONDITIONAL_SUFFIX
            resultado.append(entrada)

        # 2. Includes locales " " → resolver en disco
        for m in self._PATRON_INCLUDE_LOCAL.finditer(limpio):
            ruta_raw = m.group(1)
            resuelto = self._resolver_local(ruta_raw, archivo, raiz, include_dirs)
            if self._es_condicional(m.start(), condicionales):
                resuelto += _CONDITIONAL_SUFFIX
            resultado.append(resuelto)

        # 3. Includes dinámicos via macro → __dynamic__
        for _ in self._PATRON_INCLUDE_DYNAMIC.finditer(limpio):
            resultado.append(_DYNAMIC_MARKER)

        # 4. __has_include → siempre condicional
        for m in self._PATRON_HAS_INCLUDE.finditer(limpio):
            hdr = m.group(1) or m.group(2)
            if hdr:
                resultado.append(hdr + _CONDITIONAL_SUFFIX)

        # 5. C++20 import
        for m in self._PATRON_IMPORT_CPP20.finditer(limpio):
            resultado.append(m.group(1))

        return resultado

    # ── Resolución de includes locales ───────────────────────────────────────

    def _resolver_local(
        self,
        ruta: str,
        archivo: Path,
        raiz: Path | None,
        include_dirs: list[Path],
    ) -> str:
        """
        Busca el header en este orden:
          1. Relativo al directorio del archivo (comportamiento estándar GCC -iquote).
          2. Directorios de include del proyecto (CMake / Makefile / fallback).
        Si no lo encuentra, devuelve la ruta as-is.
        """
        # 1. Relativo al archivo fuente
        candidato = (archivo.parent / ruta).resolve()
        if candidato.exists():
            try:
                base = raiz if raiz else archivo.parent.resolve()
                return candidato.relative_to(base).as_posix()
            except ValueError:
                return str(candidato).replace("\\", "/")

        # 2. Directorios de include (CMake / Makefile / fallback)
        for base_dir in include_dirs:
            candidato = (base_dir / ruta).resolve()
            if candidato.exists():
                try:
                    base = raiz if raiz else base_dir
                    return candidato.relative_to(base).as_posix()
                except ValueError:
                    return str(candidato).replace("\\", "/")

        return ruta  # no encontrado → as-is

    # ── Carga y caché de directorios de include ───────────────────────────────

    @cached_property
    def _cache_include_dirs(self) -> dict[Path | None, list[Path]]:
        return {}

    def _include_dirs(self, raiz: Path | None) -> list[Path]:
        """
        Devuelve la lista ordenada de directorios de include del proyecto.
        Fuentes (en orden de prioridad):
          1. CMakeLists.txt de la raíz y subdirectorios inmediatos.
          2. Makefile de la raíz.
          3. Directorios estándar hardcodeados como fallback.
        Resultado cacheado por raíz.
        """
        if raiz in self._cache_include_dirs:
            return self._cache_include_dirs[raiz]

        dirs: list[Path] = []

        if raiz is not None:
            dirs.extend(self._dirs_desde_cmake(raiz))
            dirs.extend(self._dirs_desde_makefile(raiz))

            for nombre in self._INCLUDE_DIRS_FALLBACK:
                d = (raiz / nombre).resolve() if nombre else raiz.resolve()
                if d.is_dir() and d not in dirs:
                    dirs.append(d)

        self._cache_include_dirs[raiz] = dirs
        return dirs

    def _dirs_desde_cmake(self, raiz: Path) -> list[Path]:
        """
        Extrae include_directories() y target_include_directories()
        de CMakeLists.txt en la raíz y en subdirectorios de primer nivel.
        Resuelve ${CMAKE_SOURCE_DIR}, ${CMAKE_CURRENT_SOURCE_DIR},
        ${PROJECT_SOURCE_DIR} y ${CMAKE_CURRENT_LIST_DIR}.
        """
        dirs: list[Path] = []

        cmake_files = [raiz / "CMakeLists.txt"]
        cmake_files += sorted(raiz.glob("*/CMakeLists.txt"))

        for cmake_path in cmake_files:
            if not cmake_path.exists():
                continue
            try:
                contenido = cmake_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            # Sustituir comentarios de CMake
            contenido_limpio = re.sub(r"#[^\n]*", "", contenido)

            for m in self._PATRON_CMAKE_INCDIRS.finditer(contenido_limpio):
                args = m.group(1)
                for token in re.split(r"[\s\n]+", args):
                    token = token.strip().strip('"').strip("'")
                    if not token or token.upper() in self._CMAKE_KEYWORDS:
                        continue

                    # Resolución de variables CMake comunes
                    token = token.replace("${CMAKE_SOURCE_DIR}", str(raiz))
                    token = token.replace("${PROJECT_SOURCE_DIR}", str(raiz))
                    token = token.replace(
                        "${CMAKE_CURRENT_SOURCE_DIR}", str(cmake_path.parent)
                    )
                    token = token.replace(
                        "${CMAKE_CURRENT_LIST_DIR}", str(cmake_path.parent)
                    )

                    # Si quedan variables sin resolver, ignorar el token
                    if "${" in token:
                        continue

                    candidato = Path(token)
                    if not candidato.is_absolute():
                        candidato = cmake_path.parent / candidato
                    candidato = candidato.resolve()

                    if candidato.is_dir() and candidato not in dirs:
                        dirs.append(candidato)

        return dirs

    def _dirs_desde_makefile(self, raiz: Path) -> list[Path]:
        """
        Extrae rutas de -I / -isystem / -iquote del Makefile del proyecto.
        Solo procesa el primer Makefile encontrado en la raíz.
        """
        dirs: list[Path] = []
        for nombre in ("Makefile", "makefile", "GNUmakefile"):
            mk = raiz / nombre
            if not mk.exists():
                continue
            try:
                contenido = mk.read_text(encoding="utf-8", errors="replace")
            except Exception:
                break

            for m in self._PATRON_MAKEFILE_I.finditer(contenido):
                token = m.group(1).strip()
                if not token or token.startswith("$"):
                    continue
                candidato = Path(token)
                if not candidato.is_absolute():
                    candidato = (raiz / candidato).resolve()
                else:
                    candidato = candidato.resolve()
                if candidato.is_dir() and candidato not in dirs:
                    dirs.append(candidato)
            break

        return dirs

    # ── Detección de bloques condicionales ────────────────────────────────────

    def _rangos_condicionales(self, texto: str) -> list[tuple[int, int]]:
        """
        Devuelve lista de (inicio, fin) de rangos dentro de #if/#ifdef/#ifndef.
        Los includes dentro de estos rangos se etiquetan como condicionales.
        """
        rangos: list[tuple[int, int]] = []
        pila:   list[int] = []

        for m in re.finditer(
            r"""^\s*#\s*(?:(if|ifdef|ifndef)\b|(endif)\b)""",
            texto,
            re.MULTILINE,
        ):
            if m.group(1):
                pila.append(m.start())
            elif m.group(2) and pila:
                inicio = pila.pop()
                rangos.append((inicio, m.end()))

        return rangos

    @staticmethod
    def _es_condicional(pos: int, rangos: list[tuple[int, int]]) -> bool:
        return any(inicio <= pos <= fin for inicio, fin in rangos)

    # ── Detección de raíz del proyecto ────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar un marcador de proyecto C/C++."""
        marcadores = {
            "CMakeLists.txt",
            "Makefile", "makefile", "GNUmakefile",
            "configure.ac", "configure.in",
            "meson.build",
            "BUILD", "BUILD.bazel", "WORKSPACE",
            "xmake.lua", "premake5.lua",
            ".clangd",             # LSP config → raíz de proyecto
            "compile_commands.json",
        }
        actual = archivo.parent
        for _ in range(20):
            if any((actual / m).exists() for m in marcadores):
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None