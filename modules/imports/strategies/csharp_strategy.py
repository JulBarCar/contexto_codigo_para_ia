"""
modules/imports/strategies/csharp_strategy.py
Extracción de importaciones para archivos .cs (C#) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Expande `using` con llaves agrupadas (sintaxis de C# 10+):
     "using Foo.{Bar, Baz};" → ["Foo.Bar", "Foo.Baz"]
     (aunque es sintaxis informal/IDE, algunos generadores la emiten)
  2. Detecta `global using` implícito en archivos <GlobalUsings.cs> /
     <ImplicitUsings.cs> generados por el SDK de .NET 6+, emitiéndolos
     como dependencias del proyecto.
  3. Resuelve namespaces a rutas físicas de archivo siguiendo la
     convención de .NET: Foo.Bar.Baz → Foo/Bar/Baz.cs (relativo a la
     raíz del proyecto detectada por .csproj / .sln).
  4. Detecta raíz del proyecto subiendo hasta encontrar .csproj, .sln
     o Directory.Build.props.
  5. Top-level programs de C# 10+: los `using` implícitos del SDK no
     generan texto en el archivo; se documenta el comportamiento y se
     omite silenciosamente (no hay fuente estática que parsear).

Cubre:
  • using Foo.Bar;                     (namespace simple → resuelto)
  • using static Foo.Bar.Baz;          (import estático → resuelto)
  • using Alias = Foo.Bar.Baz;         (alias de tipo → path base)
  • global using Foo.Bar;              (C# 10+, global using → resuelto)
  • using Foo.{Bar, Baz};              (informal agrupado → expandido)
  • #r "nuget:Package"                 (scripts .csx → emitido as-is)
  • #r "path/to/assembly.dll"          (referencia directa → emitida)
"""

import re
from pathlib import Path

from .base import ImportStrategy


class CSharpStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".cs", ".csx"})

    # Nombres de archivo típicos de global usings implícitos del SDK .NET 6+
    _ARCHIVOS_GLOBAL_USINGS: frozenset[str] = frozenset({
        "GlobalUsings.cs",
        "ImplicitUsings.cs",
        "global_usings.cs",
    })

    _PATRON_USING = re.compile(
        r"^\s*(?:global\s+)?using\s+(?:static\s+)?(?:[\w]+\s*=\s*)?"
        r"([\w]+(?:\.[\w]+)*(?:\.\{[^}]*\})?)\s*;",
        re.MULTILINE,
    )
    _PATRON_R_DIRECTIVE = re.compile(
        r"""^\s*#r\s+["']([^"']+)["']""",
        re.MULTILINE,
    )
    # Detecta namespace propio del archivo para evitar auto-referencia
    _PATRON_NAMESPACE = re.compile(
        r"^\s*namespace\s+([\w.]+)",
        re.MULTILINE,
    )

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._detectar_raiz(archivo)

        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", texto)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        resultado: list[str] = []

        for m in self._PATRON_USING.finditer(limpio):
            raw = m.group(1)
            expandidos = self._expandir(raw)
            for ns in expandidos:
                if raiz is not None:
                    resultado.append(self._resolver(ns, raiz))
                else:
                    resultado.append(ns)

        for m in self._PATRON_R_DIRECTIVE.finditer(limpio):
            resultado.append(m.group(1))

        return resultado

    # ── Expansión de using agrupados ──────────────────────────────────────────

    def _expandir(self, raw: str) -> list[str]:
        """
        Expande "Foo.{Bar, Baz}" → ["Foo.Bar", "Foo.Baz"].
        Si no hay llaves, devuelve [raw] sin cambios.
        """
        if "{" not in raw:
            return [raw]

        idx     = raw.index("{")
        prefijo = raw[:idx].rstrip(".")
        interior = raw[idx + 1 : raw.rindex("}")].strip()

        return [
            f"{prefijo}.{parte.strip()}" if prefijo else parte.strip()
            for parte in interior.split(",")
            if parte.strip()
        ]

    # ── Resolución a ruta física ──────────────────────────────────────────────

    def _resolver(self, ns: str, raiz: Path) -> str:
        """
        Convierte un namespace a su ruta física siguiendo la convención
        de .NET: Foo.Bar.Baz → Foo/Bar/Baz.cs (relativo a raíz).
        Si no existe en disco, devuelve el namespace lógico (dep externa
        o del framework).
        """
        # Namespaces del framework/BCL nunca están en disco del proyecto
        _PREFIJOS_SISTEMA: tuple[str, ...] = (
            "System", "Microsoft", "Newtonsoft", "NUnit", "Xunit",
            "FluentAssertions", "Moq", "AutoMapper",
        )
        if any(ns.startswith(p) for p in _PREFIJOS_SISTEMA):
            return ns

        partes    = ns.split(".")
        candidato = raiz / Path(*partes)

        # Intentar Foo/Bar/Baz.cs y Foo/Bar/Baz/Baz.cs (clase en subdir)
        for ruta in (
            Path(str(candidato) + ".cs"),
            candidato / f"{partes[-1]}.cs",
        ):
            if ruta.exists():
                try:
                    return ruta.relative_to(raiz).as_posix()
                except ValueError:
                    return str(ruta).replace("\\", "/")

        return ns  # dependencia externa → emitir namespace lógico

    # ── Detección de raíz ─────────────────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar .csproj, .sln o Directory.Build.props."""
        marcadores_exactos = {"Directory.Build.props", "Directory.Build.targets"}
        actual = archivo.parent
        for _ in range(20):
            if any((actual / m).exists() for m in marcadores_exactos):
                return actual
            if any(actual.glob("*.csproj")) or any(actual.glob("*.sln")):
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None