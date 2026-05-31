"""
modules/imports/core.py
Extracción de importaciones y construcción del grafo de dependencias.

Soporta a nivel producción: Python, JS/TS/JSX/TSX/MJS/CJS, Vue, Svelte.
Soporta a nivel comercial:  Java, C#, Go, Rust, PHP, Ruby, Kotlin, Swift,
                            C/C++, Scala, Dart, R, Shell/Bash.

El dispatch por tipo de archivo está delegado al patrón Strategy.
Para agregar soporte a un nuevo lenguaje:
  1. Crear una subclase de ImportStrategy en strategies/.
  2. Registrarla en ExtractorImportaciones._strategies (o pasarla
     al constructor si se necesita una instancia personalizada).

Modo merge (fallback para lenguajes desconocidos)
─────────────────────────────────────────────────
Cuando ninguna strategy declara `soporta() = True` para un archivo,
ExtractorImportaciones ejecuta TODAS las strategies sobre el texto y
fusiona los resultados (union, preservando orden de aparición).
Esto garantiza que archivos de lenguajes aún no soportados obtengan
una extracción best-effort en lugar de retornar lista vacía.

El modo merge se puede desactivar pasando `merge_fallback=False` al
constructor, útil cuando se quiere un comportamiento estricto (vacío
si no hay strategy exacta).

Cambios respecto a la versión anterior
───────────────────────────────────────
• Nuevas strategies: Java, C#, Go, Rust, PHP, Ruby, Kotlin, Swift,
  C/C++, Scala, Dart, R, Shell/Bash.
• Modo merge: archivos sin strategy dedicada son procesados por todas
  las strategies y sus resultados se fusionan.
• VueStrategy ahora acepta `raiz` para leer components.d.ts y resolver
  auto-imports de Vite / unplugin-vue-components / Nuxt.
• SvelteStrategy reemplaza el tratamiento genérico de .svelte: resuelve
  $lib y otros aliases de SvelteKit, y descarta módulos virtuales ($app/*,
  $env/*) que no existen en disco.
• JsStrategy exporta DYNAMIC_IMPORT_MARKER ('__dynamic__'): token que
  indica un import() con template literal irresoluble estáticamente.
  _construir_grafo lo filtra antes de llamar a resolver_importacion.
"""

from pathlib import Path

from modules.aliases.loaders import cargar_aliases
from modules.aliases.resolver import resolver_importacion

from .strategies import (
    DYNAMIC_IMPORT_MARKER,
    CONDITIONAL_INCLUDE_SUFFIX,
    BUNDLER_MARKER,
    ImportStrategy,
    # Originales
    JsStrategy,
    PythonStrategy,
    SvelteStrategy,
    VueStrategy,
    # Actualizadas
    JavaStrategy,
    CSharpStrategy,
    GoStrategy,
    RustStrategy,
    PhpStrategy,
    RubyStrategy,
    KotlinStrategy,
    SwiftStrategy,
    CStrategy,
    ScalaStrategy,
    DartStrategy,
    RStrategy,
    ShellStrategy,
)

# Conjunto de marcadores especiales que _construir_grafo debe filtrar
# antes de intentar resolver en disco.
_MARCADORES_ESPECIALES: frozenset[str] = frozenset({
    DYNAMIC_IMPORT_MARKER,   # "__dynamic__"  — ruta irresoluble estáticamente
    BUNDLER_MARKER,          # "__bundler_require__" — deps de Gemfile en bloque
})


# ── Contexto (Strategy pattern) ───────────────────────────────────────────────

class ExtractorImportaciones:
    """
    Contexto del patrón Strategy.

    Selecciona automáticamente la strategy correcta para cada archivo
    y delega la extracción. El orden de la lista importa: la primera
    strategy cuyo método `soporta()` retorne True es la que se usa.

    Orden requerido:
      1. PythonStrategy   — .py  (no hay solapamiento)
      2. VueStrategy      — .vue (antes de JsStrategy; procesa JS internamente)
      3. SvelteStrategy   — .svelte (ídem)
      4. JsStrategy       — .js .ts .jsx .tsx .mjs .cjs
      5. JavaStrategy     — .java
      6. CSharpStrategy   — .cs .csx
      7. GoStrategy       — .go
      8. RustStrategy     — .rs
      9. KotlinStrategy   — .kt .kts  (antes de CStrategy para evitar conflictos)
     10. SwiftStrategy    — .swift
     11. ScalaStrategy    — .scala .sc
     12. DartStrategy     — .dart
     13. PhpStrategy      — .php y variantes
     14. RubyStrategy     — .rb .rake .gemspec .ru
     15. CStrategy        — .c .h .cpp .hpp y variantes
     16. RStrategy        — .R .r .Rmd .Rnw
     17. ShellStrategy    — .sh .bash .zsh .fish

    Modo merge (merge_fallback=True, por defecto):
      Si ninguna strategy maneja el archivo, se ejecutan TODAS y se
      fusionan los resultados. Útil para lenguajes no contemplados.

    Uso básico (la raíz se detecta automáticamente si se pasa al construir):
        extractor = ExtractorImportaciones(raiz=Path("."))
        imports = extractor.extraer(Path("src/App.vue"))

    Para inyectar strategies personalizadas (testing, extensión):
        extractor = ExtractorImportaciones(strategies=[MiStrategy()])

    Para modo estricto (sin merge fallback):
        extractor = ExtractorImportaciones(merge_fallback=False)
    """

    def __init__(
        self,
        raiz: Path | None = None,
        strategies: list[ImportStrategy] | None = None,
        merge_fallback: bool = True,
    ) -> None:
        """
        Args:
            raiz:           raíz del proyecto. Se pasa a VueStrategy y
                            SvelteStrategy para resolver auto-imports y aliases.
                            Si es None, esas features se desactivan gracefully.
            strategies:     lista de strategies a usar en orden. Si se provee,
                            `raiz` se ignora (se asume que las instancias ya
                            están configuradas).
            merge_fallback: si True (por defecto), los archivos sin strategy
                            dedicada son procesados por TODAS las strategies
                            y sus resultados se fusionan. Si False, retorna [].
        """
        self._merge_fallback = merge_fallback
        self._strategies: list[ImportStrategy] = strategies or [
            # — Originales (nivel producción) —
            PythonStrategy(),
            VueStrategy(raiz=raiz),
            SvelteStrategy(raiz=raiz),
            JsStrategy(),
            # — Nuevas (nivel comercial) —
            JavaStrategy(),
            CSharpStrategy(),
            GoStrategy(),
            RustStrategy(),
            KotlinStrategy(),   # antes de CStrategy (ambas usan sufijos sin colisión,
            SwiftStrategy(),    # pero el orden explícito evita sorpresas futuras)
            ScalaStrategy(),
            DartStrategy(),
            PhpStrategy(),
            RubyStrategy(),
            CStrategy(),
            RStrategy(),
            ShellStrategy(),
        ]

    def extraer(self, archivo: Path) -> list[str]:
        """
        Devuelve la lista deduplicada de strings de importación crudos.

        Comportamiento:
          - Si hay una strategy que soporta el archivo → la usa exclusivamente.
          - Si no hay ninguna y merge_fallback=True → ejecuta todas y fusiona.
          - Si no hay ninguna y merge_fallback=False → retorna [].
          - Si el archivo no puede leerse → retorna [].
        """
        try:
            texto = archivo.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        # Búsqueda de strategy dedicada
        for strategy in self._strategies:
            if strategy.soporta(archivo):
                return list(dict.fromkeys(strategy.extraer(archivo, texto)))

        # Modo merge: ninguna strategy declaró soporte explícito
        if not self._merge_fallback:
            return []

        return self._extraer_merge(archivo, texto)

    def _extraer_merge(self, archivo: Path, texto: str) -> list[str]:
        """
        Ejecuta todas las strategies sobre el texto y fusiona los resultados
        preservando el orden de aparición (primera strategy que detecta cada
        import tiene prioridad en posición).

        Se usa como fallback para extensiones no reconocidas por ninguna
        strategy dedicada, ofreciendo extracción best-effort.
        """
        fusionados: dict[str, None] = {}   # dict como ordered-set

        for strategy in self._strategies:
            try:
                parciales = strategy.extraer(archivo, texto)
            except Exception:
                continue
            for imp in parciales:
                fusionados[imp] = None

        return list(fusionados.keys())

    def registrar(self, strategy: ImportStrategy, *, al_inicio: bool = False) -> None:
        """
        Registra una strategy adicional en tiempo de ejecución.

        Args:
            strategy:   instancia de ImportStrategy a agregar.
            al_inicio:  si True, la strategy tiene prioridad sobre las existentes.
        """
        if al_inicio:
            self._strategies.insert(0, strategy)
        else:
            self._strategies.append(strategy)

    @property
    def extensiones_soportadas(self) -> frozenset[str]:
        """
        Devuelve el conjunto de extensiones que tienen strategy dedicada.
        Útil para diagnóstico o para decidir si activar merge_fallback.
        """
        resultado: set[str] = set()
        for strategy in self._strategies:
            if hasattr(strategy, "EXTENSIONES"):
                resultado.update(strategy.EXTENSIONES)
        return frozenset(resultado)


# ── Instancia por defecto (compatible con el contrato anterior) ───────────────

_extractor = ExtractorImportaciones()


def extraer_importaciones(archivo: Path) -> list[str]:
    """
    Función de conveniencia que mantiene la API pública original.
    Para proyectos Vue/Svelte se recomienda instanciar
    ExtractorImportaciones(raiz=raiz) directamente para habilitar
    la resolución de auto-imports y aliases.
    """
    return _extractor.extraer(archivo)


# ── Grafo de dependencias ─────────────────────────────────────────────────────

def _construir_grafo(archivos: list[Path], raiz: Path) -> list[tuple[str, list[str]]]:
    """
    Construye el grafo de dependencias internas entre los archivos del proyecto.

    Usa resolver_importacion con:
      - Un índice por ruta absoluta (evita colisiones de stem entre carpetas).
      - Los aliases leídos desde los archivos de config del proyecto.

    Filtra DYNAMIC_IMPORT_MARKER antes de llamar a resolver_importacion,
    ya que ese token no corresponde a ninguna ruta real en disco.

    Devuelve una lista de (ruta_relativa_posix, [deps_relativas_posix]).
    Solo incluye archivos que tienen al menos una dependencia interna resuelta.
    """
    # ExtractorImportaciones con raiz para habilitar Vue auto-imports y $lib
    extractor       = ExtractorImportaciones(raiz=raiz)
    indice_archivos = {a.resolve(): a.relative_to(raiz).as_posix() for a in archivos}
    aliases         = cargar_aliases(raiz)
    dep_lines: list[tuple[str, list[str]]] = []

    for archivo in archivos:
        importaciones = extractor.extraer(archivo)
        deps_internas: list[str] = []

        for imp in importaciones:
            # Ignorar marcadores especiales (dinámicos, bundler, etc.)
            # Los includes condicionales llevan sufijo __conditional__:
            # se intenta resolver el path base (sin sufijo) igualmente.
            imp_base = imp.removesuffix(CONDITIONAL_INCLUDE_SUFFIX)
            if imp_base in _MARCADORES_ESPECIALES or imp_base.startswith("__"):
                continue
            resuelto = resolver_importacion(imp_base, archivo, raiz, indice_archivos, aliases)
            if resuelto:
                deps_internas.append(resuelto)

        if deps_internas:
            rel = archivo.relative_to(raiz).as_posix()
            dep_lines.append((rel, deps_internas))

    return dep_lines