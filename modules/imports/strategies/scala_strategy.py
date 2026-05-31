"""
modules/imports/strategies/scala_strategy.py
Extracción de importaciones para archivos .scala y .sc (Scala) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Emite el path completo del import, no solo la raíz del paquete.
     Ej: "import com.example.util.Format" → "com.example.util.Format"
  2. Expande imports con llaves (Scala 2 y 3):
     "import com.example.{Foo, Bar}" → ["com.example.Foo", "com.example.Bar"]
  3. Mapea imports a rutas físicas siguiendo la convención Maven/sbt:
     src/main/scala/com/example/Foo.scala (y variantes de source set).
  4. Soporta both Scala 2 wildcard (_) y Scala 3 wildcard (*).
  5. Ignora imports dentro de bloques de comentarios de documentación
     (/** ... */) para no capturar ejemplos de código en Scaladoc.
  6. Detecta raíz del proyecto buscando build.sbt hacia arriba.

Cubre:
  • import com.example.Foo              (simple → resuelto en disco)
  • import com.example._               (Scala 2 wildcard → dir del paquete)
  • import com.example.*               (Scala 3 wildcard → dir del paquete)
  • import com.example.{Foo, Bar}      (múltiple → expandido)
  • import com.example.{Foo => Alias}  (alias → path base)
  • import scala.util.{Try, Success}   (stdlib → emitido as-is)
"""

import re
from pathlib import Path

from .base import ImportStrategy


class ScalaStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".scala", ".sc"})

    _SOURCE_SETS: tuple[str, ...] = (
        "src/main/scala",
        "src/main/java",
        "src/test/scala",
        "src/test/java",
        "src/it/scala",
    )

    _PATRON = re.compile(
        r"^\s*import\s+([\w]+(?:\.[\w*_]+)*(?:\.\{[^}]*\})?)",
        re.MULTILINE,
    )

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._raiz or self._detectar_raiz(archivo)

        # Eliminar Scaladoc (/** ... */) antes que comentarios normales
        limpio = re.sub(r"/\*\*[\s\S]*?\*/", " ", texto)
        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", limpio)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        resultado: list[str] = []
        for m in self._PATRON.finditer(limpio):
            raw = m.group(1).strip()
            expandidos = self._expandir(raw)
            for imp in expandidos:
                if raiz is not None:
                    resultado.append(self._resolver(imp, raiz))
                else:
                    resultado.append(imp)
        return resultado

    # ── Expansión de imports con llaves ───────────────────────────────────────

    def _expandir(self, raw: str) -> list[str]:
        """
        "com.example.{Foo, Bar}"  → ["com.example.Foo", "com.example.Bar"]
        "com.example.{Foo => _}"  → [] (import descartado con => _)
        "com.example._"           → ["com.example._"]
        """
        raw = re.sub(r"\s+", " ", raw).strip()

        if "{" not in raw:
            return [raw]

        idx    = raw.index("{")
        prefijo = raw[:idx].rstrip(".")
        interior = raw[idx + 1:raw.rindex("}")].strip()

        resultado: list[str] = []
        for parte in interior.split(","):
            parte = parte.strip()
            # Alias: "Foo => Bar" → usar Foo; "Foo => _" → descartar
            if "=>" in parte:
                original, alias = [p.strip() for p in parte.split("=>", 1)]
                if alias == "_":
                    continue  # import silenciado
                parte = original
            if not parte:
                continue
            resultado.append(f"{prefijo}.{parte}" if prefijo else parte)

        return resultado

    # ── Resolución a ruta física ──────────────────────────────────────────────

    def _resolver(self, imp: str, raiz: Path) -> str:
        """
        Mapea el import al archivo o directorio físico en el proyecto.
        Wildcards → directorio del paquete.
        Específicos → Foo.scala o Foo.java.
        """
        es_wildcard = imp.endswith("._") or imp.endswith(".*")

        if es_wildcard:
            pkg      = imp.rsplit(".", 1)[0]
            pkg_path = Path(*pkg.split("."))
            for ss in self._SOURCE_SETS:
                d = raiz / ss / pkg_path
                if d.is_dir():
                    try:
                        return d.relative_to(raiz).as_posix()
                    except ValueError:
                        pass
            return imp

        partes   = imp.split(".")
        pkg_path = Path(*partes[:-1]) if len(partes) > 1 else Path(".")
        clase    = partes[-1]

        for ss in self._SOURCE_SETS:
            for ext in (".scala", ".java"):
                candidato = raiz / ss / pkg_path / f"{clase}{ext}"
                if candidato.exists():
                    try:
                        return candidato.relative_to(raiz).as_posix()
                    except ValueError:
                        return str(candidato).replace("\\", "/")

        return imp  # stdlib / dep externa → emitir path lógico

    # ── Detección de raíz ─────────────────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar build.sbt o pom.xml."""
        actual = archivo.parent
        for _ in range(20):
            if (actual / "build.sbt").exists() or (actual / "pom.xml").exists():
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None