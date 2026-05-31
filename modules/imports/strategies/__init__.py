"""
modules/imports/strategies/__init__.py
Exporta las strategies disponibles y el tipo base.

Strategies registradas (en orden de prioridad en ExtractorImportaciones):
  Nivel producción (originales):
    PythonStrategy   — .py
    VueStrategy      — .vue
    SvelteStrategy   — .svelte
    JsStrategy       — .js .ts .jsx .tsx .mjs .cjs

  Nivel producción (actualizadas):
    JavaStrategy     — .java               (+ resolución Maven/Gradle, import static)
    CSharpStrategy   — .cs .csx            (+ using agrupados, resolución .csproj)
    GoStrategy       — .go                 (sin cambios)
    RustStrategy     — .rs                 (sin cambios)
    PhpStrategy      — .php y variantes    (+ use agrupados, resolución PSR-4/Composer)
    RubyStrategy     — .rb .rake ...       (+ require_relative resuelto, Gemfile)
    KotlinStrategy   — .kt .kts            (sin cambios)
    SwiftStrategy    — .swift              (reescritura completa; era copia de Kotlin)
    CStrategy        — .c .h .cpp .hpp ... (+ resolución local, __conditional__)
    ScalaStrategy    — .scala .sc          (sin cambios)
    DartStrategy     — .dart               (sin cambios)
    RStrategy        — .R .r .Rmd .Rnw    (+ resolución source(), DESCRIPTION)
    ShellStrategy    — .sh .bash .zsh ...  (+ source estático/dinámico, type -P, hash)

Marcadores especiales:
    DYNAMIC_IMPORT_MARKER    = "__dynamic__"
        Emitido cuando hay un import/require/source con ruta dinámica
        no resoluble estáticamente (template literals JS, $VAR en Shell, etc.)
    CONDITIONAL_INCLUDE_SUFFIX = "__conditional__"
        Sufijo añadido a includes de C/C++ y imports de Swift dentro de
        bloques #if / #ifdef / #ifndef / canImport(). Indica dependencia
        opcional / condicional de plataforma.
    BUNDLER_MARKER           = "__bundler_require__"
        Emitido por RubyStrategy cuando detecta Bundler.require o
        require 'bundler/setup', indicando que todas las gems del Gemfile
        son dependencias del archivo.
"""

from .base import ImportStrategy
from .js_strategy import JsStrategy, DYNAMIC_IMPORT_MARKER
from .python_strategy import PythonStrategy
from .svelte_strategy import SvelteStrategy
from .vue_strategy import VueStrategy

# Strategies actualizadas
from .java_strategy import JavaStrategy
from .csharp_strategy import CSharpStrategy
from .go_strategy import GoStrategy
from .rust_strategy import RustStrategy
from .php_strategy import PhpStrategy, _DYNAMIC_MARKER as PHP_DYNAMIC_MARKER
from .ruby_strategy import RubyStrategy, _BUNDLER_MARKER as BUNDLER_MARKER
from .kotlin_strategy import KotlinStrategy
from .swift_strategy import SwiftStrategy, _CONDITIONAL_SUFFIX as CONDITIONAL_INCLUDE_SUFFIX
from .c_strategy import CStrategy, _DYNAMIC_MARKER as C_DYNAMIC_MARKER, _CONDITIONAL_SUFFIX
from .scala_strategy import ScalaStrategy
from .dart_strategy import DartStrategy
from .r_strategy import RStrategy, _DYNAMIC_MARKER as R_DYNAMIC_MARKER
from .shell_strategy import ShellStrategy, _DYNAMIC_MARKER as SHELL_DYNAMIC_MARKER

__all__ = [
    # Base
    "ImportStrategy",
    # Marcadores
    "DYNAMIC_IMPORT_MARKER",
    "CONDITIONAL_INCLUDE_SUFFIX",
    "BUNDLER_MARKER",
    # Originales
    "PythonStrategy",
    "JsStrategy",
    "VueStrategy",
    "SvelteStrategy",
    # Actualizadas
    "JavaStrategy",
    "CSharpStrategy",
    "GoStrategy",
    "RustStrategy",
    "PhpStrategy",
    "RubyStrategy",
    "KotlinStrategy",
    "SwiftStrategy",
    "CStrategy",
    "ScalaStrategy",
    "DartStrategy",
    "RStrategy",
    "ShellStrategy",
]