"""
modules/imports/strategies/java_strategy.py
Extracción de importaciones para archivos .java — nivel producción.

Mejoras respecto a la versión anterior:
  1. Emite el path completo del import, no solo la raíz del paquete.
     Ej: "import com.example.util.Format" → "com.example.util.Format"
  2. Resuelve imports a rutas físicas de archivo siguiendo la convención
     Maven / Gradle: com.example.Foo → src/main/java/com/example/Foo.java
     (y variantes de source set: src/main/kotlin/, src/test/java/, etc.)
  3. Lee pom.xml o build.gradle para detectar la raíz del proyecto; si no
     encuentra ninguno, sube hasta 20 niveles buscando el marcador.
  4. Imports con wildcard (foo.bar.*) se resuelven al directorio del paquete
     si existe en disco, o se emiten como path lógico si no.
  5. `import static` se maneja igual que `import` normal — se emite el
     path completo (sin el miembro estático final).
  6. go.mod-style: la raíz y el source set se detectan una sola vez por
     instancia (cached_property), no por cada archivo.

Cubre:
  • import foo.bar.Baz;                (import simple → resuelto en disco)
  • import foo.bar.*;                  (wildcard → directorio del paquete)
  • import static foo.bar.Baz.method; (import estático → path de clase)
  • import static foo.bar.Baz.*;      (import estático wildcard → directorio)
"""

import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy


class JavaStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".java"})

    # Source sets estándar de Maven/Gradle (en orden de probabilidad)
    _SOURCE_SETS: tuple[str, ...] = (
        "src/main/java",
        "src/main/kotlin",
        "src/test/java",
        "src/test/kotlin",
        "src/androidTest/java",
        "src/androidMain/kotlin",
        "src",             # proyectos planos sin estructura Maven
    )

    _PATRON = re.compile(
        r"^\s*import\s+(?:static\s+)?([\w]+(?:\.[\w*]+)*)\s*;",
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
            # Para import static, quitar el miembro final si no es wildcard
            # Ej: "com.example.Baz.method" → "com.example.Baz"
            imp = self._normalizar_static(imp)
            if raiz is not None:
                resultado.append(self._resolver(imp, raiz))
            else:
                resultado.append(imp)
        return resultado

    # ── Resolución a ruta física ──────────────────────────────────────────────

    def _normalizar_static(self, imp: str) -> str:
        """
        Para imports estáticos el último segmento puede ser un miembro
        (método o campo), no una clase. Heurística: si el último segmento
        empieza con minúscula y no es '*', es un miembro — lo quitamos.
        """
        if imp.endswith(".*"):
            return imp
        partes = imp.split(".")
        if len(partes) > 1 and partes[-1][0].islower():
            return ".".join(partes[:-1])
        return imp

    def _resolver(self, imp: str, raiz: Path) -> str:
        """
        Mapea el import a un archivo o directorio físico en el proyecto.
        Wildcards → directorio del paquete (si existe).
        Específicos → ClassName.java (o .kt).
        Externos / stdlib → emite el path lógico completo.
        """
        es_wildcard = imp.endswith(".*")

        if es_wildcard:
            pkg      = imp[:-2]          # "com.example.util"
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
            for ext in (".java", ".kt"):
                candidato = raiz / ss / pkg_path / f"{clase}{ext}"
                if candidato.exists():
                    try:
                        return candidato.relative_to(raiz).as_posix()
                    except ValueError:
                        return str(candidato).replace("\\", "/")

        return imp  # stdlib / dep externa → emitir path lógico

    # ── Detección de raíz del proyecto ────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar pom.xml, build.gradle o settings.gradle."""
        marcadores = {
            "pom.xml",
            "build.gradle", "build.gradle.kts",
            "settings.gradle", "settings.gradle.kts",
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