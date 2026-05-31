"""
modules/imports/strategies/kotlin_strategy.py
Extracción de importaciones para archivos .kt y .kts (Kotlin) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Emite el path completo del import, no solo la raíz.
     Ej: "import com.example.util.Format" → "com.example.util.Format"
  2. Detecta la raíz del proyecto leyendo settings.gradle / settings.gradle.kts
     y build.gradle / build.gradle.kts para inferir el source set.
  3. Mapea imports a rutas físicas de archivo siguiendo la convención
     de Maven / Gradle: com.example.Foo → src/main/kotlin/com/example/Foo.kt
     (y variantes: src/main/java/, src/commonMain/kotlin/, etc.)
  4. Si el import NO resuelve a un archivo del proyecto, se emite el
     path completo del paquete para que resolver_importacion lo descarte
     (dependencia externa, stdlib de Kotlin/Java, etc.).
  5. Soporta .kts (scripts de Gradle y otros) además de .kt.

Cubre:
  • import com.example.Foo              (import completo → resuelto en disco)
  • import com.example.*               (wildcard → emitido como paquete)
  • import com.example.Foo as Bar      (alias → path base emitido)
  • @file:Suppress(...)               (anotación de archivo, ignorada)
"""

import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy


class KotlinStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".kt", ".kts"})

    # Source sets estándar de Gradle (en orden de probabilidad)
    _SOURCE_SETS: tuple[str, ...] = (
        "src/main/kotlin",
        "src/main/java",
        "src/commonMain/kotlin",
        "src/commonMain/java",
        "src/androidMain/kotlin",
        "src/iosMain/kotlin",
        "src/test/kotlin",
        "src/test/java",
    )

    _PATRON = re.compile(
        r"^\s*import\s+([\w]+(?:\.[\w*]+)*)(?:\s+as\s+\w+)?\s*$",
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

        resultado: list[str] = []
        for m in self._PATRON.finditer(limpio):
            imp = m.group(1)
            if raiz is not None:
                resuelto = self._resolver(imp, raiz)
                resultado.append(resuelto)
            else:
                resultado.append(imp)
        return resultado

    # ── Resolución de import a ruta física ────────────────────────────────────

    def _resolver(self, imp: str, raiz: Path) -> str:
        """
        Intenta mapear el import a un archivo .kt o .java en el proyecto.
        Si no encuentra nada, devuelve el path completo del paquete.
        """
        if imp.endswith(".*"):
            # Wildcard: emitir como directorio si existe
            pkg_path = Path(*imp[:-2].split("."))
            for source_set in self._SOURCE_SETS:
                dir_pkg = raiz / source_set / pkg_path
                if dir_pkg.is_dir():
                    try:
                        return dir_pkg.relative_to(raiz).as_posix()
                    except ValueError:
                        pass
            return imp

        # Import específico: buscar Foo.kt o Foo.java
        partes    = imp.split(".")
        pkg_path  = Path(*partes[:-1]) if len(partes) > 1 else Path(".")
        clase     = partes[-1]

        for source_set in self._SOURCE_SETS:
            for ext in (".kt", ".java"):
                candidato = raiz / source_set / pkg_path / f"{clase}{ext}"
                if candidato.exists():
                    try:
                        return candidato.relative_to(raiz).as_posix()
                    except ValueError:
                        return str(candidato).replace("\\", "/")

        return imp  # dependencia externa / stdlib → emitir path lógico

    # ── Detección de raíz del proyecto ────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar settings.gradle, build.gradle o gradlew."""
        marcadores = {
            "settings.gradle", "settings.gradle.kts",
            "build.gradle",    "build.gradle.kts",
            "gradlew",
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